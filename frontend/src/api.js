async function asJson(res) {
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export async function sendChat(message) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  return asJson(res);
}

export async function ingestText(content) {
  const res = await fetch("/api/documents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  return asJson(res);
}

export async function uploadFile(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/documents/upload", {
    method: "POST",
    body: form,
  });
  return asJson(res);
}

export async function listDocuments() {
  const res = await fetch("/api/documents");
  return asJson(res);
}

export async function deleteDocument(id) {
  const res = await fetch(`/api/documents/${id}`, { method: "DELETE" });
  return asJson(res);
}
