const express = require("express");
const app = express();

app.use(express.json());

let licenses = [];

function generateLicense(duration) {
  const rand = Math.random().toString(36).substring(2, 10).toUpperCase();
  return `PRO-${duration}-${rand}`;
}

// ======================
// 💰 코드 자동 생성 API
// ======================
app.post("/payment-success", (req, res) => {

  const duration = req.body.duration;

  const code = generateLicense(duration);

  licenses.push({
    code: code,
    duration: duration,
    activated: false,
    device: null,
    expire: null
  });

  console.log("🆕 코드 생성:", code);

  res.json({ code: code });
});

// 코드 목록 확인
app.get("/licenses", (req, res) => {
  res.json(licenses);
});

// 서버 확인용
app.get("/", (req, res) => {
  res.send("License Server Running 🚀");
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log("License server running on port " + PORT);
});
