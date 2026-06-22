import { sanitizeDescriptionHtml } from "./htmlSanitizer";

export function HtmlDescription({ html, className }: { html: string; className?: string }) {
  return (
    <div
      className={className}
      dangerouslySetInnerHTML={{ __html: sanitizeDescriptionHtml(html) }}
    />
  );
}
