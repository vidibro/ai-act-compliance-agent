// The guide page: the theme switch, a button that copies the whole guide as Markdown, and a copy
// button on each code block so the template can be taken in one click.

function setTheme(theme) {
  if (theme === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  try { theme === "auto" ? localStorage.removeItem("theme") : localStorage.setItem("theme", theme); } catch {}
  for (const b of document.querySelectorAll("#theme button")) b.classList.toggle("on", b.dataset.theme === theme);
}

// The clipboard API first; where the browser withholds it, the older copy command on a hidden
// text field.
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return;
  } catch {}
  const field = document.createElement("textarea");
  field.value = text;
  field.setAttribute("readonly", "");
  field.style.position = "fixed";
  field.style.opacity = "0";
  document.body.append(field);
  field.select();
  const copied = document.execCommand("copy");
  field.remove();
  if (!copied) throw new Error("copy refused");
}

function addCopyButton(pre) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "copy";
  button.textContent = "Copy";
  button.addEventListener("click", async () => {
    try {
      await copyText(pre.querySelector("code")?.textContent ?? pre.textContent);
      button.textContent = "Copied";
    } catch {
      button.textContent = "Copy failed";
    }
    setTimeout(() => { button.textContent = "Copy"; }, 1500);
  });
  pre.append(button);
}

// Fetched up front: the clipboard write has to follow the click directly, and a fetch in between
// loses the click's permission in some browsers.
const markdown = fetch("/guide.md").then((r) => (r.ok ? r.text() : Promise.reject(new Error(r.statusText))));

async function copyGuide(button) {
  try {
    await copyText(await markdown);
    button.textContent = "Copied";
  } catch {
    button.textContent = "Copy failed";
  }
  setTimeout(() => { button.textContent = "Copy as Markdown"; }, 1500);
}

window.addEventListener("DOMContentLoaded", () => {
  const copy = document.getElementById("copy-guide");
  copy.addEventListener("click", () => copyGuide(copy));
  for (const b of document.querySelectorAll("#theme button")) b.addEventListener("click", () => setTheme(b.dataset.theme));
  setTheme(document.documentElement.dataset.theme || "auto");
  for (const pre of document.querySelectorAll(".guide pre")) addCopyButton(pre);
});
