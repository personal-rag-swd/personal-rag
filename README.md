# Personal RAG Studio (Aviary) — Software Requirements Specification

> Tài liệu này vừa là README kỹ thuật, vừa đóng vai trò Đặc tả Yêu cầu Phần mềm (SRS) cho đồ án SWD392. Nó mô tả mục đích, phạm vi, yêu cầu chức năng/phi chức năng, kiến trúc, mô hình dữ liệu và giao diện của hệ thống **Personal RAG Studio (Aviary)**.

---

## Mục lục

1. [Giới thiệu](#1-giới-thiệu)
2. [Mô tả tổng quan hệ thống](#2-mô-tả-tổng-quan-hệ-thống)
3. [Yêu cầu chức năng](#3-yêu-cầu-chức-năng)
4. [Yêu cầu phi chức năng](#4-yêu-cầu-phi-chức-năng)
5. [Kiến trúc hệ thống](#5-kiến-trúc-hệ-thống)
6. [Mô hình dữ liệu](#6-mô-hình-dữ-liệu)
7. [Giao diện ngoài (External Interfaces)](#7-giao-diện-ngoài-external-interfaces)
8. [Công nghệ sử dụng](#8-công-nghệ-sử-dụng)
9. [Cấu trúc mã nguồn](#9-cấu-trúc-mã-nguồn)
10. [Cài đặt & vận hành](#10-cài-đặt--vận-hành)
11. [Kiểm thử & chất lượng](#11-kiểm-thử--chất-lượng)
12. [Phụ lục: Cấu hình môi trường](#12-phụ-lục-cấu-hình-môi-trường)

---

## 1. Giới thiệu

### 1.1 Mục đích (Purpose)

Personal RAG Studio (tên nội bộ **Aviary**) là một ứng dụng **Retrieval-Augmented Generation (RAG)** cho phép người dùng tạo "notebook" nghiên cứu/học tập, tải lên tài liệu (PDF, DOCX, TXT, Markdown), trò chuyện với một AI agent được "grounded" (neo giữ ngữ cảnh) trên chính các tài liệu đó kèm trích dẫn nguồn, và tự động sinh ra các sản phẩm học tập có cấu trúc: quiz, flashcard, mind map, và báo cáo (report).

Tài liệu này xác định:
- Phạm vi chức năng của hệ thống.
- Các actor (vai trò người dùng) và use case chính.
- Yêu cầu phi chức năng (hiệu năng, bảo mật, khả năng mở rộng).
- Kiến trúc kỹ thuật và mô hình dữ liệu làm cơ sở cho việc phát triển, kiểm thử và bảo trì.

### 1.2 Phạm vi (Scope)

Hệ thống gồm hai thành phần chính triển khai độc lập:
- **Backend**: FastAPI (Python), lưu trữ dữ liệu bằng MongoDB (qua Beanie ODM), lưu file bằng MinIO/S3, xử lý bất đồng bộ qua RabbitMQ, tích hợp LLM qua OpenRouter (Pydantic AI).
- **Frontend**: SPA React 19 + Vite + Tailwind CSS + shadcn/ui, giao tiếp với backend qua REST API và Server-Sent Events (SSE).

Ngoài lõi RAG, hệ thống còn bao gồm: xác thực người dùng (OTP + JWT), quản lý vai trò (RBAC: `user` / `admin`), thanh toán/subscription theo gói (Polar.sh), và một trang quản trị (Admin Dashboard) để theo dõi người dùng, tài liệu và doanh thu sử dụng.

### 1.3 Đối tượng sử dụng tài liệu

- Sinh viên/nhóm phát triển (dùng làm tài liệu tham chiếu khi code, review, chấm điểm SWD392).
- Người vận hành (DevOps) khi triển khai production.
- Người đánh giá/giảng viên khi review đặc tả yêu cầu.

### 1.4 Định nghĩa, thuật ngữ viết tắt

| Thuật ngữ | Ý nghĩa |
|---|---|
| RAG | Retrieval-Augmented Generation — sinh câu trả lời có neo giữ trên tài liệu truy hồi được |
| Notebook | Không gian làm việc chứa tài liệu, chat history, và report của một chủ đề nghiên cứu |
| Chunk | Đoạn văn bản nhỏ được cắt ra từ tài liệu, có vector embedding, dùng để tìm kiếm ngữ nghĩa |
| Embedding | Vector số thực biểu diễn ngữ nghĩa của một đoạn văn bản |
| Atlas Vector Search | Tính năng tìm kiếm vector gốc của MongoDB Atlas (`$vectorSearch`) |
| Tier | Gói dịch vụ: Free / Pro / Max, quyết định giới hạn token sử dụng |
| SSE | Server-Sent Events — kênh đẩy sự kiện thời gian thực từ server xuống client |
| RBAC | Role-Based Access Control — phân quyền theo vai trò (`user`, `admin`) |

---

## 2. Mô tả tổng quan hệ thống

### 2.1 Góc nhìn sản phẩm (Product Perspective)

Aviary là một hệ thống độc lập (không phụ thuộc hệ thống lớn hơn), triển khai dạng web app, sử dụng các dịch vụ bên thứ ba sau:

| Dịch vụ ngoài | Vai trò |
|---|---|
| OpenRouter | Cổng truy cập LLM cho chat, rewrite câu hỏi, sinh report có cấu trúc, và embedding |
| MongoDB Atlas | Cơ sở dữ liệu chính + Atlas Vector Search cho semantic search |
| MinIO / AWS S3 | Lưu trữ file tài liệu gốc do người dùng upload |
| RabbitMQ | Message broker cho pipeline ingest tài liệu bất đồng bộ |
| Resend | Gửi email OTP xác thực đăng ký / đặt lại mật khẩu |
| Polar.sh | Cổng thanh toán subscription (Pro/Max) và đo lường usage-based billing |

### 2.2 Nhóm người dùng (User Classes)

| Actor | Mô tả |
|---|---|
| **Guest** | Người dùng chưa đăng nhập; chỉ truy cập được trang đăng ký/đăng nhập |
| **User** (role `user`) | Người dùng đã xác thực; tạo/quản lý notebook riêng của mình, chat, sinh report, quản lý subscription của chính mình |
| **Admin** (role `admin`) | Có toàn bộ quyền của User, cộng thêm quyền xem thống kê hệ thống, danh sách người dùng/tài liệu toàn hệ thống, cập nhật vai trò/trạng thái người dùng, xem tổng quan doanh thu billing |

### 2.3 Ràng buộc thiết kế (Design Constraints)

- Backend chỉ hỗ trợ **một** nhà cung cấp LLM đã được nối dây tại một thời điểm: **OpenRouter** (`chat_provider_is_configured()` chặn tính năng chat với lỗi 503 thân thiện nếu chưa cấu hình).
- MongoDB Atlas Vector Search index (`notebook_chunks_vector_index`) được quản lý **thủ công ngoài version control** — mọi filter path mới trong code (hiện có: `notebook_id`, `user_id`, `document_id`) phải được thêm vào Atlas Search Index ở **mọi môi trường** trước khi deploy.
- Giới hạn kích thước tài liệu ingest: tối đa 50MB/tệp, tối đa 5000 chunk/tài liệu (chống lạm dụng chi phí embedding).
- Không có bộ test runner cho frontend; việc kiểm tra dựa trên `lint` + `typecheck` + kiểm thử thủ công.

### 2.4 Giả định & phụ thuộc (Assumptions & Dependencies)

- Người dùng có kết nối Internet ổn định (ứng dụng phụ thuộc real-time streaming SSE và gọi LLM ngoài).
- MongoDB được cấu hình ở chế độ Atlas (production) để có `$vectorSearch`; môi trường dev có thể dùng MongoDB thường + `mongomock-motor` cho test.
- Chi phí LLM/embedding được kiểm soát qua cơ chế allowance theo tier, không phải giới hạn cứng ở tầng hạ tầng.

---

## 3. Yêu cầu chức năng

Mỗi yêu cầu được đánh mã `FR-<module>-<số>` để tiện truy vết trong quá trình test.

### 3.1 Xác thực & tài khoản (`auth`, `users`)

| Mã | Yêu cầu |
|---|---|
| FR-AUTH-01 | Hệ thống phải cho phép người dùng đăng ký bằng email + mật khẩu, gửi mã OTP xác thực qua email (Resend) trước khi tạo tài khoản chính thức (`PendingRegistration` → `User`). |
| FR-AUTH-02 | Hệ thống phải giới hạn số lần nhập sai OTP (`otp_max_attempts`, mặc định 5) và thời gian hết hạn OTP (`otp_expire_minutes`, mặc định 10 phút). |
| FR-AUTH-03 | Hệ thống phải cấp JWT access token (ngắn hạn) và refresh token xoay vòng (rotating refresh token) khi đăng nhập thành công; refresh token có thể thu hồi (`DELETE` session). |
| FR-AUTH-04 | Hệ thống phải hỗ trợ luồng đặt lại mật khẩu qua OTP xác minh email. |
| FR-AUTH-05 | Hệ thống phải xác thực người dùng qua header `Authorization: Bearer` **hoặc** cookie `access_token`. |
| FR-USER-01 | Người dùng đã đăng nhập có thể xem thông tin hồ sơ của chính mình (`GET /users/me`). |
| FR-USER-02 | Hệ thống phải hỗ trợ RBAC với tối thiểu hai vai trò: `user` và `admin`, chặn truy cập endpoint quản trị nếu vai trò không đủ quyền. |

### 3.2 Quản lý Notebook (`notebooks`)

| Mã | Yêu cầu |
|---|---|
| FR-NB-01 | Người dùng phải tạo được notebook mới với tên, mô tả và tags. |
| FR-NB-02 | Người dùng phải xem được danh sách notebook của mình, cập nhật (đổi tên/mô tả/tags), và xoá notebook (kèm toàn bộ tài liệu/chunk/report/chat history liên quan). |
| FR-NB-03 | Hệ thống phải cập nhật `last_active_at` của notebook mỗi khi có tương tác (endpoint `touch`), phục vụ sắp xếp "gần đây". |
| FR-NB-04 | Người dùng phải xem được toàn bộ dữ liệu tổng hợp của một notebook (tài liệu + report) qua một endpoint "populate" duy nhất để giảm số lượt gọi API khi mở trang notebook. |

### 3.3 Nạp tài liệu (Document Ingestion) (`file`, `notebooks/rag`)

| Mã | Yêu cầu |
|---|---|
| FR-ING-01 | Hệ thống phải cấp presigned URL để client upload file **trực tiếp** lên MinIO/S3 (không qua backend), hỗ trợ theo dõi tiến độ upload. |
| FR-ING-02 | Hệ thống phải hỗ trợ nạp các định dạng: `.pdf` (PyMuPDF/pymupdf4llm, giữ định dạng markdown), `.docx` (đoạn văn + bảng), `.txt`, `.md`. |
| FR-ING-03 | Hệ thống phải hỗ trợ ghi chú dạng rich-text nhập trực tiếp trong notebook ("Notes"), được chunk & index như tài liệu upload thông thường. |
| FR-ING-04 | Vòng đời trạng thái tài liệu phải tuân theo: `pending → uploaded → processing → indexed`, hoặc `failed` khi có lỗi; tài liệu "kẹt" quá lâu ở trạng thái trung gian phải được đánh dấu `failed` tự động (stale timeout, mặc định 15 phút). |
| FR-ING-05 | Khi có sự kiện `ObjectCreated` từ MinIO qua RabbitMQ, hệ thống phải tự động: claim tài liệu → tải nội dung từ S3 → cắt chunk (`notebook_chunk_size`=1000, `overlap`=200) → sinh embedding qua OpenRouter → lưu `NotebookDocumentChunk` → đánh dấu `indexed`. |
| FR-ING-06 | Khi RabbitMQ consumer bị tắt (`RABBITMQ_CONSUMER_ENABLED=false`, mặc định), hệ thống phải tự poll các tài liệu `pending`/`uploaded` để xử lý (cơ chế fallback). |
| FR-ING-07 | Hệ thống phải giới hạn kích thước tài liệu (mặc định 50MB) và số chunk tối đa/tài liệu (mặc định 5000) để tránh chi phí embedding vượt kiểm soát. |
| FR-ING-08 | Người dùng phải xem/tải xuống được tài liệu gốc, xem trước PDF inline, và xem nội dung từng chunk đã index (phục vụ debug/minh bạch nguồn trích dẫn). |
| FR-ING-09 | Người dùng phải xoá được một tài liệu cụ thể khỏi notebook (kèm toàn bộ chunk liên quan). |

### 3.4 Chat & Truy hồi (RAG) (`notebooks/agent`, `notebooks/rag`)

| Mã | Yêu cầu |
|---|---|
| FR-CHAT-01 | Hệ thống phải cung cấp giao diện chat theo notebook, agent (Pydantic AI) chủ động gọi tool `search_notebook_context` để truy hồi ngữ cảnh liên quan từ chunk đã index trước khi trả lời. |
| FR-CHAT-02 | Hệ thống phải hỗ trợ viết lại câu hỏi người dùng (query rewrite) trước khi vector search, khi `ENABLE_QUERY_REWRITE=true`, nhằm cải thiện độ chính xác truy hồi với câu hỏi hội thoại không rõ ràng. |
| FR-CHAT-03 | Truy hồi phải dùng MongoDB Atlas `$vectorSearch` trên trường `embedding`, cho phép lọc phạm vi theo `notebook_id`, `user_id`, và tuỳ chọn `document_id` (chat khoanh vùng một tài liệu cụ thể). |
| FR-CHAT-04 | Phản hồi chat phải được stream về client theo giao thức AG-UI (Server-Sent Events), không chặn (block) toàn bộ phản hồi tới khi generate xong. |
| FR-CHAT-05 | Lịch sử chat phải được lưu lại theo notebook (`NotebookMessage`), và được cắt bớt (`keep_recent` ≈ 15 tin nhắn non-system gần nhất) mỗi lượt để giới hạn kích thước ngữ cảnh gửi cho LLM. |
| FR-CHAT-06 | Người dùng phải xoá được toàn bộ lịch sử chat của một notebook. |
| FR-CHAT-07 | Hệ thống phải phát sự kiện thời gian thực (SSE, `GET /notebooks/events`) cho tiến trình ingest tài liệu (`processing → indexing → indexed`) và tiến trình sinh report, để frontend cập nhật UI không cần polling. |

### 3.5 Sinh nội dung học tập (Report Generation) (`notebooks/agent/report_agents`)

Hệ thống phải hỗ trợ sinh 7 loại report có cấu trúc, mỗi loại được validate theo Pydantic model riêng trước khi trả về:

| Mã | Loại report | Yêu cầu nội dung |
|---|---|---|
| FR-REP-01 | `briefing` | Tóm tắt điều hành (`executive_summary`), các điểm chính (`key_takeaways`), hàm ý chiến lược (`strategic_implications`) |
| FR-REP-02 | `study_guide` | Bảng thuật ngữ (glossary) + bộ quiz đi kèm để tự kiểm tra |
| FR-REP-03 | `blog` | Bài viết dạng blog: tiêu đề, đoạn mở đầu thu hút (hook), nội dung markdown |
| FR-REP-04 | `custom` | Nội dung markdown tự do theo chỉ dẫn bổ sung (`additional_instructions`) của người dùng |
| FR-REP-05 | `mindmap` | Sơ đồ tư duy dạng cây: chủ đề trung tâm, các node (root/main/sub) có `parent_id`, và các quan hệ chéo (`relationships`) giữa node — hiển thị bằng ReactFlow ở frontend |
| FR-REP-06 | `quiz` | Bộ câu hỏi trắc nghiệm; mỗi câu có đúng 4 lựa chọn, `correct_index` hợp lệ (0–3), và giải thích bám sát nguồn tài liệu |
| FR-REP-07 | `flashcards` | Bộ thẻ ghi nhớ (front/back), số lượng cấu hình được (`number_of_cards`) |
| FR-REP-08 | Người dùng phải chọn được mức độ chi tiết (`detail_level`) và chỉ dẫn bổ sung khi khởi tạo report. |
| FR-REP-09 | Report phải chạy như tác vụ nền (`BackgroundTasks`), có trạng thái `pending → generating → completed`/`failed`, và có thể **huỷ** (`cancel`) khi đang chạy. |
| FR-REP-10 | Khi server khởi động lại giữa lúc có report đang `pending`/`generating`, hệ thống phải tự động khôi phục và tiếp tục xử lý (`_recover_pending_reports()`). |
| FR-REP-11 | Người dùng phải xem được danh sách report của một notebook, xem chi tiết, và xoá report. |

### 3.6 Thanh toán & Gói dịch vụ (`billing`)

| Mã | Yêu cầu |
|---|---|
| FR-BILL-01 | Hệ thống phải cung cấp 3 gói: **Free**, **Pro** ($20/tháng), **Max** ($100/tháng), mỗi gói có giới hạn token LLM riêng theo tháng, theo phiên (session, cửa sổ 5 giờ) và theo tuần (cửa sổ 7 ngày). |
| FR-BILL-02 | Người dùng phải tạo được phiên thanh toán (checkout session) qua Polar.sh để nâng cấp gói, và chuyển đổi gói (`change-plan`) khi đã có subscription. |
| FR-BILL-03 | Người dùng phải truy cập được cổng tự quản (Customer Portal) của Polar để quản lý phương thức thanh toán/huỷ gói. |
| FR-BILL-04 | Hệ thống phải nhận và xác thực webhook từ Polar (`POST /billing/webhooks/polar`), cập nhật trạng thái subscription (`BillingCustomer`), và đảm bảo **idempotent** (không xử lý trùng lặp cùng một `webhook_id`, dùng `ProcessedWebhookEvent`). |
| FR-BILL-05 | Mỗi lượt sử dụng LLM (chat, sinh report) phải được ghi nhận vào `UsageEventLog` với `idempotency_key`, và đẩy lên Polar dưới dạng usage-based billing event theo lô định kỳ (`polar_usage_emit_interval_seconds`), có cơ chế retry (tối đa `polar_usage_emit_max_retries` lần). |
| FR-BILL-06 | Hệ thống phải chặn (gate) một lượt gọi LLM nếu vượt quá **bất kỳ** giới hạn nào trong 3 cửa sổ (tháng/phiên/tuần) đang áp dụng cho tier hiện tại của người dùng, và trả về thời điểm giới hạn được reset. |
| FR-BILL-07 | Giới hạn allowance hiệu lực (effective allowance) phải được tính **động** từ cấu hình (`Settings`) tại mỗi lần kiểm tra dựa trên tier hiện tại của người dùng — **không** lưu snapshot giới hạn cũ theo user. Hệ quả: khi vận hành tăng giới hạn cho một tier, toàn bộ người dùng đang ở tier đó được áp dụng giới hạn mới ngay lập tức, không cần migration hay chờ chu kỳ billing mới. |
| FR-BILL-08 | Nếu subscription có `product_id` không khớp với tier Pro/Max đã biết, hệ thống phải suy giảm về giới hạn Free (không bao giờ suy giảm về "không giới hạn"). |
| FR-BILL-09 | Người dùng phải xem được tổng quan sử dụng hiện tại (`GET /billing/usage`): số token đã dùng/còn lại theo từng cửa sổ, thời điểm reset. |

### 3.7 Quản trị hệ thống (`admin`)

| Mã | Yêu cầu |
|---|---|
| FR-ADM-01 | Chỉ tài khoản có vai trò `admin` mới truy cập được các endpoint dưới `/admin/*`. |
| FR-ADM-02 | Admin phải xem được thống kê tổng quan hệ thống (`/admin/stats`): tổng số người dùng, tài liệu, v.v. |
| FR-ADM-03 | Admin phải xem được biểu đồ sử dụng theo ngày (`/admin/usage/daily`). |
| FR-ADM-04 | Admin phải xem được danh sách người dùng (phân trang/lọc) và cập nhật thông tin người dùng (vai trò, trạng thái active). |
| FR-ADM-05 | Admin phải xem được usage chi tiết của một người dùng cụ thể. |
| FR-ADM-06 | Admin phải xem được danh sách tài liệu toàn hệ thống. |
| FR-ADM-07 | Admin phải xem được tổng quan doanh thu/billing (`/admin/billing/summary`). |

---

## 4. Yêu cầu phi chức năng

| Mã | Hạng mục | Yêu cầu |
|---|---|---|
| NFR-01 | Hiệu năng | API server phải không bị chặn (non-blocking) trong lúc ingest tài liệu — toàn bộ pipeline ingest chạy bất đồng bộ qua RabbitMQ consumer hoặc polling nền, tách biệt khỏi request-response cycle. |
| NFR-02 | Khả năng mở rộng | Ingestion phải chịu được nhiều tài liệu đồng thời qua hàng đợi (RabbitMQ `prefetch_count`), với dead-letter queue cho message lỗi. |
| NFR-03 | Độ tin cậy | Ingest và xử lý webhook phải "at-least-once nhưng idempotent": trùng lặp sự kiện (RabbitMQ redelivery, Polar webhook retry) không được gây side-effect kép. |
| NFR-04 | Bảo mật | Mật khẩu phải được hash (không lưu plaintext); JWT access token ngắn hạn + refresh token xoay vòng, có thể thu hồi; secrets (JWT key, Polar keys, DB URL) không được commit vào git (`.env` bị gitignore). |
| NFR-05 | Bảo mật | Đăng ký tài khoản phải xác thực quyền sở hữu email qua OTP trước khi tạo user. |
| NFR-06 | Quan sát được (Observability) | Toàn bộ backend phải tích hợp telemetry (Logfire/OpenTelemetry) để theo dõi lỗi và hiệu năng ở production. |
| NFR-07 | Khả năng bảo trì | Route handler phải mỏng (thin); toàn bộ business logic nằm ở tầng `service`, theo khuôn mẫu `models/schemas/service/router` cho mỗi feature module. |
| NFR-08 | Khả năng dùng lại | MongoDB Atlas Vector Search index phải hỗ trợ mở rộng thêm filter path mới mà không cần đổi schema code, miễn là cập nhật định nghĩa index tương ứng. |
| NFR-09 | Trải nghiệm người dùng | Tiến trình ingest tài liệu và sinh report phải phản hồi trạng thái thời gian thực (SSE) thay vì yêu cầu người dùng tải lại trang. |
| NFR-10 | Giới hạn chi phí | Giới hạn cứng số byte/tài liệu và số chunk/tài liệu nhằm chặn chi phí embedding bất thường từ một lượt upload. |
| NFR-11 | Khả năng kiểm thử | Test backend phải chạy trên MongoDB thật + MinIO thật (không mock hoàn toàn), đảm bảo hành vi gần với production nhất có thể trong CI. |

---

## 5. Kiến trúc hệ thống

Hệ thống dùng mô hình **upload trực tiếp lên S3** kết hợp **pipeline ingest hướng sự kiện (event-driven)** để giữ cho API server luôn phản hồi nhanh.

```mermaid
graph TD
    %% Styling
    classDef frontend fill:#3b82f6,stroke:#1d4ed8,color:#fff
    classDef storage fill:#10b981,stroke:#047857,color:#fff
    classDef backend fill:#f59e0b,stroke:#b45309,color:#fff
    classDef mq fill:#8b5cf6,stroke:#6d28d9,color:#fff
    classDef db fill:#ec4899,stroke:#be185d,color:#fff

    %% Components
    FE[React 19 Frontend]:::frontend
    S3[MinIO / S3 Storage]:::storage
    RMQ[RabbitMQ Broker]:::mq
    BE[FastAPI Backend]:::backend
    MDB[MongoDB & Beanie]:::db
    PAI[Pydantic AI / LLM]:::backend

    %% Direct upload flow
    FE -->|1. Request Presigned URL| BE
    BE -->|2. Return Presigned URL| FE
    FE -->|3. Direct PUT Upload| S3

    %% Event Ingestion Loop
    S3 -->|4. ObjectCreated Event| RMQ
    RMQ -->|5. Deliver Notification| BE
    BE -->|6. Fetch & Parse File| S3
    BE -->|7. Chunk & Save Chunks| MDB
    BE -->|8. Wait for Atlas Vector Index| MDB

    %% RAG Search & Generation Flow
    FE -->|9. Submit Chat / Generate Report| BE
    BE -->|10. Rewrite Query| PAI
    BE -->|11. Atlas Vector Search| MDB
    BE -->|12. Generate Structured Output| PAI
    PAI -->|13. Return Answer / Report| BE
    BE -->|14. Respond SSE / JSON| FE
```

### 5.1 Luồng upload trực tiếp lên S3

- Frontend yêu cầu presigned URL từ backend (`POST /api/v1/file/presigned-url`).
- Frontend upload file thẳng lên **MinIO / S3** bằng `PUT` qua `XMLHttpRequest` (hỗ trợ theo dõi tiến độ).
- Sau khi upload thành công, tài liệu được đăng ký trong **MongoDB** với trạng thái `uploaded`.

### 5.2 Vòng lặp ingest bất đồng bộ

- MinIO phát sự kiện `ObjectCreated` qua **RabbitMQ** (AMQP notification exchange).
- Consumer nền của FastAPI (chuyển sang **FastStream**, thay cho `aio-pika` thuần trước đây) xử lý message từ queue.
- Consumer claim tài liệu (`processing`), đọc từ MinIO, trích xuất văn bản bằng parser chuyên biệt, cắt chunk, và lưu vào MongoDB.
- Ở môi trường Atlas, worker chờ (`indexing`) tới khi Atlas Vector Search index build xong và có thể tìm kiếm được, rồi mới đánh dấu `indexed`.
- *Fallback*: nếu tắt RabbitMQ, scheduler poll MongoDB tìm file `pending`/`uploaded` để xử lý nền.

### 5.3 Luồng truy hồi & sinh nội dung (Pydantic AI Agents)

- **Tối ưu truy vấn**: câu hỏi người dùng được viết lại bởi agent tìm kiếm chuyên biệt (`query_rewrite_agent`) để loại bỏ từ ngữ hội thoại dư thừa, giữ lại từ khoá cốt lõi.
- **Atlas Vector Search**: MongoDB Atlas xử lý tìm kiếm ngữ nghĩa (`$vectorSearch`) với embedding sinh phía client (qua OpenRouter).
- **Sinh nội dung có cấu trúc**: các study agent sinh phản hồi có cấu trúc (Quiz, Flashcard, Mind Map, Report...) ánh xạ trực tiếp vào Pydantic model (`output_type`), được validate/sanitize trước khi trả về người dùng.

---

## 6. Mô hình dữ liệu

Toàn bộ entity là Beanie `Document` (MongoDB), khoá chính `id: UUID` (lưu dạng BSON `Binary`).

### 6.1 Auth & Users

- **User**: `email`, `hashed_password`, `role` (`user`|`admin`), `is_active`.
- **PendingRegistration**: hồ sơ đăng ký chờ xác thực OTP.
- **RefreshToken**: refresh token xoay vòng, có thể thu hồi.

### 6.2 Notebooks

- **Notebook**: `user_id`, `name`, `description`, `tags`, `last_active_at`.
- **NotebookDocument**: `notebook_id`, `user_id`, `s3_bucket`/`s3_key` hoặc `content` (note nội bộ), `status` (`pending`→`uploaded`→`processing`→`indexed`|`failed`).
- **NotebookDocumentChunk**: `document_id`, `notebook_id`, `user_id`, `chunk_index`, `content`, `embedding: list[float]`, `chunk_metadata`.
- **NotebookMessage**: `notebook_id`, `seq`, `message` (payload AG-UI).
- **NotebookReport**: `notebook_id`, `user_id`, `report_type`, `status` (`pending`→`generating`→`completed`|`failed`), `content: dict` (payload theo từng loại report ở mục 3.5).

### 6.3 Billing

- **BillingCustomer**: `user_id`, `polar_customer_id`, `subscription_id`, `subscription_status`, `product_id`, `current_period_start/end`.
- **UsageEventLog**: `user_id`, `notebook_id`, `quantity` (token), `idempotency_key`, trạng thái đẩy lên Polar (`polar_ingested`, `retry_count`).
- **UsageAllowance**: bộ đếm token theo tháng (free-tier gating), `period_start/end`, `llm_tokens_used`.
- **UsageWindowCounter**: bộ đếm theo cửa sổ trượt (`session` 5h / `weekly` 7 ngày), không cố định theo lịch.
- **ProcessedWebhookEvent**: chống xử lý trùng webhook Polar (idempotency theo `webhook_id`).

### 6.4 Sơ đồ quan hệ (rút gọn)

```
User 1---* Notebook 1---* NotebookDocument 1---* NotebookDocumentChunk
User 1---* Notebook 1---* NotebookMessage
User 1---* Notebook 1---* NotebookReport
User 1---1 BillingCustomer 1---* UsageEventLog
User 1---1 UsageAllowance (theo tháng)
User 1---* UsageWindowCounter (theo session/weekly)
```

---

## 7. Giao diện ngoài (External Interfaces)

### 7.1 API chính (mount dưới `/api/v1`)

| Nhóm | Endpoint tiêu biểu |
|---|---|
| Auth | `POST /auth/registrations`, `POST /auth/email-verifications`, `POST /auth/sessions`, `POST /auth/token-refreshes`, `POST /auth/password-resets`, `DELETE /auth/sessions` |
| Users | `GET /users/me`, `GET /users/` |
| File | `POST /file/presigned-url`, `POST /file/upload-failed` |
| Notebooks | `GET|POST /notebooks/`, `GET|PATCH|DELETE /notebooks/{id}`, `GET /notebooks/{id}/documents`, `GET /notebooks/{id}/populate`, `GET /notebooks/events` (SSE) |
| Documents | `GET /notebooks/{id}/documents/{doc_id}/pdf-inline`, `.../download`, `.../chunks/{chunk_index}` |
| Chat | `POST /notebooks/{id}/chat` (stream AG-UI), `DELETE /notebooks/{id}/chat/history` |
| Reports | `POST /notebooks/{id}/reports`, `GET /notebooks/{id}/reports`, `GET /notebooks/{id}/reports/{report_id}`, `POST .../cancel`, `DELETE .../{report_id}` |
| Billing | `POST /billing/checkout`, `POST /billing/change-plan`, `GET /billing/portal`, `GET /billing/usage`, `GET /billing/subscription`, `POST /billing/webhooks/polar` |
| Admin | `GET /admin/stats`, `GET /admin/usage/daily`, `GET|PATCH /admin/users`, `GET /admin/users/{id}/usage`, `GET /admin/documents`, `GET /admin/billing/summary` |

Đầy đủ hợp đồng API (schema, request/response mẫu) có sẵn qua **Scalar API Docs** tại `http://localhost:8000/docs` khi chạy dev server.

### 7.2 Giao diện người dùng

- SPA React, routing qua `react-router` (`front-end/src/routes.tsx`).
- Các trang chính: Đăng nhập/Đăng ký, Dashboard (danh sách notebook), Notebook Page (tài liệu + chat + report), Trang cài đặt Billing, Trang quản trị Admin (chỉ role `admin`).
- Giao tiếp real-time qua SSE (`@assistant-ui/react-ag-ui` cho chat streaming; event bus riêng cho ingest/report).

### 7.3 Giao diện phần cứng/phần mềm khác

- Không có yêu cầu phần cứng đặc biệt; chạy trên máy chủ Linux container (Docker) hoặc máy dev Windows/Mac/Linux.
- Yêu cầu network outbound tới: OpenRouter, MongoDB Atlas (nếu dùng cloud), Resend, Polar.sh.

---

## 8. Công nghệ sử dụng

### Backend
- **FastAPI** — web framework bất đồng bộ hiệu năng cao.
- **Beanie ODM** — Object Document Mapper cho MongoDB, dựa trên `motor` + Pydantic v2.
- **Pydantic AI** — framework xây dựng ứng dụng LLM, model-agnostic.
- **RabbitMQ / FastStream** — xử lý sự kiện MinIO bất đồng bộ.
- **PyMuPDF & PyMuPDF4LLM** — trích xuất văn bản/layout PDF dạng markdown.
- **python-docx** — parse file DOCX.
- **Logfire / OpenTelemetry** — quan sát và giám sát hệ thống.
- **Polar SDK** — tích hợp thanh toán & usage-based billing.

### Frontend
- **React 19** — component & state hooks hiện đại.
- **Vite** — bundling & hot reload nhanh.
- **Tailwind CSS** — utility-first styling.
- **TanStack Query** — quản lý server state (fetch/cache/sync).
- **Zustand** — state quản lý phía client theo feature.
- **shadcn/ui** — hệ thống thiết kế UI.
- **ReactFlow** — hiển thị mind map dạng node tương tác.
- **@assistant-ui/react + react-ag-ui** — giao diện chat streaming.

---

## 9. Cấu trúc mã nguồn

```text
.
├── back-end/               # FastAPI Backend Service
│   ├── app/
│   │   ├── admin/          # Thống kê & quản trị hệ thống (chỉ role admin)
│   │   ├── auth/           # Đăng ký OTP, đăng nhập JWT, refresh token
│   │   ├── users/          # Hồ sơ người dùng & RBAC
│   │   ├── file/           # Presigned URL upload & callback trạng thái
│   │   ├── billing/        # Subscription, usage metering, webhook Polar
│   │   ├── notebooks/      # Lõi RAG
│   │   │   ├── agent/      # Pydantic AI Chat & Report Agents
│   │   │   ├── memory/     # Lịch sử chat & converter AGUI
│   │   │   ├── prompt/     # System prompt templates
│   │   │   ├── rag/        # Chunking, ingestion worker, Atlas Vector Search
│   │   │   └── tools/      # Tool tìm kiếm ngữ cảnh cho agent
│   │   ├── core/           # Config, DB/Beanie init, S3 client, telemetry
│   │   └── utils/          # Helper dùng chung
│   ├── tests/               # Bộ test Pytest
│   ├── pyproject.toml
│   └── uv.lock
├── front-end/               # Vite + React 19 SPA
│   └── src/
│       ├── components/ui/  # Thành phần shadcn/ui
│       ├── features/       # auth, dashboard, files, notebooks, billing, admin
│       ├── hooks/
│       ├── lib/             # Axios client, queryClient, utils
│       └── routes.tsx
├── docker-compose.yml       # Stack dev (MongoDB, RabbitMQ, MinIO, Backend, Frontend)
├── docker-compose.prod.yml  # Compose production
├── DOKPLOY_DEPLOYMENT.md    # Hướng dẫn deploy Dokploy
└── AGENTS.md                # Quy ước code & đóng góp
```

---

## 10. Cài đặt & vận hành

### Yêu cầu môi trường
- Docker & Docker Compose.
- Node.js (v18+) & npm (nếu chạy frontend trên host).
- Python 3.11+ & `uv` (nếu chạy backend trên host).

### Chạy bằng Docker Compose (khuyến nghị)

```bash
cp .env.example .env
docker compose up --build
```

Truy cập:
- Frontend: `http://localhost:5173`
- Backend API Docs (Scalar): `http://localhost:8000/docs`
- MinIO Console: `http://localhost:9001` (`minioadmin` / `minioadmin`)

### Chạy thủ công (hybrid)

```bash
# Hạ tầng
docker compose up -d mongodb minio rabbitmq minio-mc

# Backend
cd back-end
ln -sf ../.env .env
uv sync
uv run fastapi dev app/main.py

# Frontend
cd front-end
npm install
npm run dev
```

---

## 11. Kiểm thử & chất lượng

### Backend (từ `back-end/`)
- `uv run pytest` — chạy toàn bộ test (dùng MongoDB thật `personal-rag-test` + MinIO thật `personal-rag-test` bucket; CI cấp cả hai qua service container).
- `uv run ruff check` / `uv run ruff format` — lint / format (line length 88, ruleset nghiêm ngặt).
- `npx pyright --pythonpath .venv/bin/python` — type check.

### Frontend (từ `front-end/`)
- `npm run lint`, `npm run typecheck`, `npm run build` (= `tsc -b && vite build`), `npm run format`.
- Không có test runner riêng cho frontend — thay đổi UI được xác nhận bằng lint + typecheck + kiểm thử thủ công trên trình duyệt.

### CI/CD
`.github/workflows/ci.yml` chạy `uv run pytest` (backend) và `npm run lint` + `npm run build` (frontend) trên mọi PR vào `master`.

---

## 12. Phụ lục: Cấu hình môi trường

Copy `.env.example` thành `.env` ở thư mục gốc và điền giá trị thật:

```ini
# Database configuration (MongoDB)
DATABASE_URL=mongodb://localhost:27017/personal-rag

# Authentication & Security
JWT_SECRET_KEY=change-me-to-a-32-byte-dev-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
OTP_EXPIRE_MINUTES=10
OTP_MAX_ATTEMPTS=5

# LLM Providers (Pydantic AI / OpenRouter)
CHAT_API_KEY=your-openrouter-api-key
CHAT_MODEL=openai/gpt-4o-mini

# Embedding Settings (MongoDB Atlas Vector Search)
EMBEDDING_MODEL=google/gemini-embedding-2
EMBEDDING_DIMENSION=1536

# Object Storage (MinIO)
S3_BUCKET=personal-rag-bucket
S3_REGION=us-east-1
S3_ENDPOINT_URL=http://localhost:9000
S3_PUBLIC_ENDPOINT_URL=http://localhost:9000
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin

# RabbitMQ / Message Broker Eventing
RABBITMQ_CONSUMER_ENABLED=true
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
RABBITMQ_QUEUE_NAME=notebook-document-ingestion

# Billing (Polar.sh)
POLAR_API_KEY=
POLAR_WEBHOOK_SECRET=
POLAR_PRO_PRODUCT_ID=
POLAR_MAX_PRODUCT_ID=
FREE_TIER_LLM_TOKENS_ALLOWANCE=200000
PRO_TIER_LLM_TOKENS_ALLOWANCE=20000000
MAX_TIER_LLM_TOKENS_ALLOWANCE=140000000
```

> Lưu ý: giá trị allowance ở trên chỉ là **giá trị mặc định** trong `Settings`/`.env.example` — thay đổi được tại runtime qua biến môi trường cùng tên mà không cần sửa code, và áp dụng ngay cho toàn bộ người dùng đang ở tier tương ứng (xem FR-BILL-07).
