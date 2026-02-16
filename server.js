const express = require("express");
const app = express();

app.use(express.json());

const PORT = process.env.PORT || 3000;

let users = {};
let keys = {};

app.get("/", (req, res) => {
  res.json({ status: "MCR License Server Running" });
});

app.post("/signup", (req, res) => {
  const { id, pw } = req.body;

  if (!id || !pw)
    return res.json({ success: false });

  if (users[id])
    return res.json({ success: false });

  users[id] = { pw, expire: 0, pc: null };
  res.json({ success: true });
});

app.post("/login", (req, res) => {
  const { id, pw } = req.body;
  const user = users[id];

  if (!user || user.pw !== pw)
    return res.json({ success: false });

  let remain = 0;

  if (user.expire > Date.now())
    remain = Math.ceil((user.expire - Date.now()) / 86400000);

  res.json({ success: true, remain_days: remain });
});

app.post("/generate_key", (req, res) => {
  const { days = 30 } = req.body;

  const key =
    "KEY-" +
    Math.random().toString(36).substring(2, 10).toUpperCase();

  keys[key] = { days, used: false };

  res.json({ success: true, key });
});

app.post("/use_key", (req, res) => {
  const { id, key, pc } = req.body;

  const user = users[id];
  const k = keys[key];

  if (!user || !k || k.used)
    return res.json({ success: false });

  user.expire = Date.now() + k.days * 86400000;
  user.pc = pc;
  k.used = true;

  res.json({ success: true });
});

app.post("/check", (req, res) => {
  const { id, pc } = req.body;
  const user = users[id];

  if (!user) return res.json({ valid: false });

  if (user.pc && user.pc !== pc)
    return res.json({ valid: false });

  if (user.expire < Date.now())
    return res.json({ valid: false });

  res.json({ valid: true });
});

app.listen(PORT, () => {
  console.log("Server running on port " + PORT);
});
