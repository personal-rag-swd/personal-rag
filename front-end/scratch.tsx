import { renderToStaticMarkup } from "react-dom/server";
import { StreamdownTextPrimitive } from "@assistant-ui/react-streamdown";

const Test = () => (
  <StreamdownTextPrimitive
    preprocess={() => "[1](cite:test:0)"}
    components={{
      a: (props) => <div>A: {JSON.stringify(props)}</div>
    }}
  />
);
console.log(renderToStaticMarkup(<Test />));
