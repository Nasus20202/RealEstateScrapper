const ALLOWED_TAGS = new Set([
  "A",
  "B",
  "BR",
  "DIV",
  "EM",
  "H2",
  "H3",
  "H4",
  "I",
  "LI",
  "OL",
  "P",
  "SPAN",
  "STRONG",
  "U",
  "UL",
]);

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function looksLikeHtml(value: string): boolean {
  return /<\/?[a-z][\s\S]*>/i.test(value);
}

function isSafeHref(value: string): boolean {
  return /^(https?:|mailto:|tel:|\/)/i.test(value);
}

export function sanitizeDescriptionHtml(value: string): string {
  if (!looksLikeHtml(value)) {
    return escapeHtml(value).replace(/\r?\n/g, "<br />");
  }

  const template = document.createElement("template");
  template.innerHTML = value;

  const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_ELEMENT);
  const nodes: Element[] = [];
  while (walker.nextNode()) nodes.push(walker.currentNode as Element);

  for (const node of nodes.reverse()) {
    if (!ALLOWED_TAGS.has(node.tagName)) {
      node.replaceWith(...Array.from(node.childNodes));
      continue;
    }

    for (const attr of Array.from(node.attributes)) {
      if (node.tagName === "A" && attr.name === "href" && isSafeHref(attr.value)) continue;
      node.removeAttribute(attr.name);
    }

    if (node.tagName === "A") {
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noreferrer");
    }
  }

  return template.innerHTML;
}
