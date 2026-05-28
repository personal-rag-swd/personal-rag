import { renderToStaticMarkup } from "react-dom/server";
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";

const Test = () => (
  <MarkdownTextPrimitive
    components={{
      a: (props) => <div>A: {JSON.stringify(props)}</div>
    }}
  >
    {"[1](cite:test:0)"}
  </MarkdownTextPrimitive>
);
console.log(renderToStaticMarkup(<Test />));
