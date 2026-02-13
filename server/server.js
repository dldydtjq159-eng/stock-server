const express = require("express");
const app = express();

app.use(express.json());

let licenses = [
  {
    code: "PRO-30D-AAAA1111",
    duration: "30D",
    activated: false,
    device: null,
    expire: null
  }
];

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

app.post("/activate", (req, res) => {
  const { code, device } = req.body;

  const lic = licenses.find(l => l.code === code);

  if (!lic)
    return res.json({ success: false });

  if (!lic.activated) {
    lic.activated = true;
    lic.device = device;
    lic.expire = getExpire(lic.duration);
  }

  if (lic.device !== device)
    return res.json({ success: false });

  if (lic.expire && new Date() > lic.expire)
    return res.json({ success: false });

  res.json({ success: true });
});

app.listen(3000, () =>
  console.log("License server running")
);
