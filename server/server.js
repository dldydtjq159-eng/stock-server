const express = require("express");
const app = express();

app.use(express.json());

// ======================
// 🗄 라이센스 저장소 (DB 대신 메모리)
// ======================

app.get("/", (req, res) => {
  res.send("License Server Running 🔐");
});

let licenses = [];


// ======================
// 🔑 코드 자동 생성
// ======================

function generateLicense(duration) {

  const rand = Math.random()
    .toString(36)
    .substring(2, 10)
    .toUpperCase();

  return `PRO-${duration}-${rand}`;
}


// ======================
// ⏳ 만료일 계산
// ======================

function getExpire(duration) {

  let now = new Date();

  if (duration === "7D")
    now.setDate(now.getDate() + 7);

  if (duration === "30D")
    now.setDate(now.getDate() + 30);

  if (duration === "LIFE")
    return null;

  return now;
}


// ======================
// 💰 결제 성공 → 코드 자동 생성
// ======================

app.post("/payment-success", (req, res) => {

  const duration = req.body.duration; // "7D", "30D", "LIFE"

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


// ======================
// 🔐 프로그램 인증 API
// ======================

app.post("/activate", (req, res) => {

  const { code, device } = req.body;

  const lic = licenses.find(l => l.code === code);

  if (!lic) {
    return res.json({ success: false, reason: "INVALID_CODE" });
  }

  // 첫 활성화
  if (!lic.activated) {
    lic.activated = true;
    lic.device = device;
    lic.expire = getExpire(lic.duration);
  }

  // 다른 PC에서 사용 시 차단
  if (lic.device !== device) {
    return res.json({ success: false, reason: "DEVICE_MISMATCH" });
  }

  // 만료 확인
  if (lic.expire && new Date() > lic.expire) {
    return res.json({ success: false, reason: "EXPIRED" });
  }

  res.json({ success: true });
});


// ======================
// 📊 코드 목록 확인 (관리자용)
// ======================

app.get("/licenses", (req, res) => {
  res.json(licenses);
});


// ======================
// 🚀 서버 시작
// ======================

app.listen(3000, () => {
  console.log("🔥 License server running on http://localhost:3000");
});
