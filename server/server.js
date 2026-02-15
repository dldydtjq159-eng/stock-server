const express = require("express");
const fs = require("fs");

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;

const DB_FILE = "db.json";

// --------------------
// DB 로드 / 저장
// --------------------
function loadDB() {
  if (!fs.existsSync(DB_FILE)) {
    fs.writeFileSync(DB_FILE, JSON.stringify({ users: [], keys: [] }));
  }
  return JSON.parse(fs.readFileSync(DB_FILE));
}

function saveDB(data) {
  fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2));
}

// --------------------
// 서버 확인용
// --------------------
app.get("/", (req, res) => {
  res.send("🔥 MCR License Server Running");
});

// --------------------
// 회원가입
// --------------------
app.post("/signup", (req, res) => {
  const { id, pw } = req.body;

  const db = loadDB();

  if (db.users.find(u => u.id === id)) {
    return res.json({ success: false, msg: "이미 존재" });
  }

  db.users.push({ id, pw, expire: 0 });
  saveDB(db);

  res.json({ success: true });
});

// --------------------
// 로그인
// --------------------
app.post("/login", (req, res) => {
  const { id, pw } = req.body;

  const db = loadDB();

  const user = db.users.find(u => u.id === id && u.pw === pw);

  if (!user) return res.json({ success: false });

  const now = Date.now();

  if (user.expire > now) {
    return res.json({
      success: true,
      valid: true,
      remain: Math.floor((user.expire - now) / 86400000)
    });
  }

  res.json({ success: true, valid: false });
});

// --------------------
// 코드 등록 (기간 연장)
// --------------------
app.post("/activate", (req, res) => {
  const { id, code } = req.body;

  const db = loadDB();

  const key = db.keys.find(k => k.code === code && !k.used);

  if (!key) return res.json({ success: false });

  const user = db.users.find(u => u.id === id);
  if (!user) return res.json({ success: false });

  const now = Date.now();

  user.expire = Math.max(user.expire, now) + key.days * 86400000;

  key.used = true;

  saveDB(db);

  res.json({ success: true });
});

// --------------------
// 관리자 키 생성
// --------------------
app.post("/admin/generate", (req, res) => {
  const { days } = req.body;

  const db = loadDB();

  const code = "KEY-" + Math.random().toString(36).substr(2, 8).toUpperCase();

  db.keys.push({
    code,
    days,
    used: false
  });

  saveDB(db);

  res.json({ code });
});

app.listen(PORT, () => {
  console.log("Server running on port " + PORT);
});
