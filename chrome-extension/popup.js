fetch("http://127.0.0.1:8765/health", {
  cache: "no-store",
  headers: { "X-Onur-Helper": "1" }
})
  .then((response) => response.json())
  .then(() => {
    document.querySelector("#status").textContent = "Yerel uygulama bağlı";
  })
  .catch(() => {
    document.querySelector("#status").textContent = "Yerel uygulama kapalı";
  });
