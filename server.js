const express = require("express");
const app = express();

app.use(express.json());

const PORT = process.env.PORT || 3000;

// 서버 상태 확인
app.get("/", (req, res) => {
  res.json({ status: "MCR License Server Running" });
});

// 테스트용 API
app.get("/test", (req, res) => {
  res.json({ ok: true });
});

app.listen(PORT, () => {
  console.log("Server running on port " + PORT);
});
