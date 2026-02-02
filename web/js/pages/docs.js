const docLinks = Array.from(document.querySelectorAll(".doc-link"));
const docContent = document.getElementById("doc-content");
const docOutline = document.getElementById("doc-outline");

function setActiveLink(target) {
  docLinks.forEach((link) => {
    link.classList.toggle("active", link === target);
  });
}

function renderOutline() {
  if (!docContent || !docOutline) {
    return;
  }
  docOutline.textContent = "";
  const headings = docContent.querySelectorAll("h2, h3");
  if (!headings.length) {
    docOutline.textContent = "No sections available.";
    return;
  }

  headings.forEach((heading) => {
    const id = heading.id || heading.textContent.replace(/\s+/g, "-").toLowerCase();
    heading.id = id;
    const link = document.createElement("a");
    link.className = "toc-link";
    link.href = `#${id}`;
    link.textContent = heading.textContent;
    link.addEventListener("click", (e) => {
      e.preventDefault();
      heading.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    docOutline.appendChild(link);
  });
}

async function loadDoc(path, link) {
  if (!docContent) {
    return;
  }
  try {
    const response = await fetch(`/${path}`);
    if (!response.ok) {
      throw new Error("Doc not found");
    }
    const html = await response.text();
    docContent.innerHTML = sanitizeHtml(html);
    setActiveLink(link);
    renderOutline();
  } catch (error) {
    docContent.textContent = "Unable to load documentation.";
    docOutline.textContent = "";
  }
}

function init() {
  if (!docLinks.length) {
    return;
  }
  docLinks.forEach((link) => {
    link.addEventListener("click", () => {
      loadDoc(link.dataset.doc, link);
    });
  });
  loadDoc(docLinks[0].dataset.doc, docLinks[0]);
}

document.addEventListener("DOMContentLoaded", init);

function sanitizeHtml(html) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, "text/html");
  const forbiddenTags = ["script", "iframe", "object", "embed", "link", "style"];

  forbiddenTags.forEach((tag) => {
    doc.querySelectorAll(tag).forEach((node) => node.remove());
  });

  doc.querySelectorAll("*").forEach((node) => {
    [...node.attributes].forEach((attr) => {
      const name = attr.name.toLowerCase();
      const value = attr.value || "";
      if (name.startsWith("on")) {
        node.removeAttribute(attr.name);
      }
      if ((name === "href" || name === "src") && value.includes("javascript:")) {
        node.removeAttribute(attr.name);
      }
    });
  });

  return doc.body.innerHTML;
}
