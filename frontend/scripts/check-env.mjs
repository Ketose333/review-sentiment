const value = process.env.NEXT_PUBLIC_API_URL;

function invalid(reason) {
  throw new Error(`NEXT_PUBLIC_API_URL ${reason}. Set it to the browser-accessible API origin.`);
}

if (!value || value !== value.trim()) invalid("is missing or has surrounding whitespace");

let url;
try {
  url = new URL(value);
} catch {
  invalid("is not a valid absolute URL");
}

const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
if (url.protocol !== "https:" && !(local && url.protocol === "http:")) {
  invalid("must use HTTPS, except for localhost development");
}
if (url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
  invalid("must be an origin without credentials, path, query, or fragment");
}

console.log("NEXT_PUBLIC_API_URL: valid");
