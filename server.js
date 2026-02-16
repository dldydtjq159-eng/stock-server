const express = require("express");
const app = express();

app.use(express.json());

const PORT = process.env.PORT || 3000;

// ===== 임시 DB =====
let keys = {
  "TEST-1234": { used:false }
};

// 서버 확인
app.get("/", (req,res)=>{
  res.json({ status:"MCR License Server Running" });
});

// 키 검증
app.post("/verify",(req,res)=>{

  const { key } = req.body;

  if(!keys[key])
    return res.json({ success:false, msg:"키 없음" });

  if(keys[key].used)
    return res.json({ success:false, msg:"이미 사용됨" });

  keys[key].used = true;

  res.json({ success:true });
});

app.listen(PORT,()=>{
  console.log("Server running on port "+PORT);
});