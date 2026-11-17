#!/bin/bash
# Lightsail 시작 스크립트: nginx 설치 + Qlens 대시보드 배포 (dashboard/index.html 내용을 그대로 포함)
apt-get update -y
apt-get install -y nginx
cat > /var/www/html/index.html <<'QLENS_EOF'
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Qlens 품질 대시보드</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root { --bg:#f5f6f8; --card:#fff; --text:#1d2330; --muted:#6b7280; --line:#e5e7eb;
          --ok:#16a34a; --def:#dc2626; --accent:#2563eb; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system, "Segoe UI", "Malgun Gothic", sans-serif; background:var(--bg); color:var(--text); }
  header { background:#111827; color:#fff; padding:16px 24px; display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
  header h1 { margin:0; font-size:20px; } header h1 span { color:#93c5fd; }
  header small { color:#9ca3af; }
  main { max-width:1200px; margin:0 auto; padding:20px 16px 40px; }
  .kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:12px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; }
  .kpi .label { color:var(--muted); font-size:13px; } .kpi .value { font-size:28px; font-weight:700; margin-top:4px; }
  .charts { display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:12px; margin-top:12px; }
  .card h2 { margin:0 0 12px; font-size:15px; }
  .chart-box { position:relative; height:260px; }
  table { width:100%; border-collapse:collapse; font-size:14px; }
  th, td { text-align:left; padding:8px; border-bottom:1px solid var(--line); vertical-align:top; }
  th { color:var(--muted); font-weight:600; font-size:12px; }
  .table-wrap { overflow-x:auto; }
  .badge { display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; font-weight:700; color:#fff; }
  .badge.DEFECT { background:var(--def); } .badge.OK { background:var(--ok); } .badge.UNKNOWN { background:#6b7280; } .badge.REVIEW { background:#d97706; }
  .toolbar { display:flex; gap:8px; align-items:center; margin:12px 0; flex-wrap:wrap; }
  button, select { font:inherit; padding:6px 12px; border:1px solid var(--line); border-radius:6px; background:#fff; cursor:pointer; }
  .error { color:var(--def); margin-top:12px; white-space:pre-wrap; }
  .reason { color:var(--muted); max-width:420px; }
  td:nth-child(4), td:nth-child(5), td:nth-child(6) { white-space:nowrap; }
  .toasts { position:fixed; right:16px; bottom:16px; display:flex; flex-direction:column; gap:10px; z-index:50; max-width:min(380px, calc(100vw - 32px)); }
  .toast { background:#fff; border:1px solid var(--line); border-left:6px solid var(--ok); border-radius:10px; padding:12px 14px;
           box-shadow:0 8px 24px rgba(0,0,0,.15); animation:slidein .25s ease-out; cursor:pointer; }
  .toast.DEFECT { border-left-color:var(--def); }
  .toast.REVIEW { border-left-color:#d97706; }
  .toast b { display:block; font-size:15px; margin-bottom:2px; }
  .toast small { color:var(--muted); display:block; margin-top:4px; }
  .flash { animation:flash 1.2s ease-out; }
  @keyframes slidein { from { transform:translateX(30px); opacity:0; } to { transform:none; opacity:1; } }
  @keyframes flash { 0% { background:#fee2e2; } 100% { background:transparent; } }
  @media (prefers-reduced-motion: reduce) { .toast, .flash { animation:none; } }
  .demo { display:flex; flex-wrap:wrap; align-items:center; gap:12px 24px; margin-bottom:12px; border-left:0; background:#eef4ff; }
  .demo h2 { margin:0 0 4px; }
  .demo p { margin:0; color:var(--muted); font-size:14px; }
  .demo > div:first-child { flex:1 1 360px; }
  .demo-btns { display:flex; gap:8px; flex-wrap:wrap; }
  .demo-btn { font-weight:700; color:#fff; border:0; padding:10px 16px; border-radius:8px; }
  .demo-btn.ok { background:var(--ok); } .demo-btn.def { background:var(--def); }
  .demo-btn:disabled { opacity:.5; cursor:wait; }
  .demo-status { flex-basis:100%; font-size:13px; color:var(--text); min-height:18px; }
</style>
</head>
<body>
<header>
  <div><h1><span>Q</span>lens 품질 검사 대시보드</h1><small>Amazon Bedrock 기반 주조 부품 불량 판정</small></div>
  <small id="updated">-</small>
</header>
<div class="toasts" id="toasts" aria-live="assertive"></div>
<main>
  <section class="card demo">
    <div>
      <h2>🧪 직접 테스트해 보기</h2>
      <p>버튼을 누르면 Kaggle 샘플 부품 사진이 S3에 업로드되고, AI(Bedrock)가 판정해 <b>수 초 안에</b> 결과가 팝업과 표에 표시됩니다.</p>
    </div>
    <div class="demo-btns">
      <button type="button" class="demo-btn ok" data-kind="ok">✔ 정상 샘플 검사</button>
      <button type="button" class="demo-btn def" data-kind="defect">✖ 불량 샘플 검사</button>
    </div>
    <div class="demo-status" id="demo-status" aria-live="polite"></div>
  </section>

  <section class="kpis">
    <div class="card kpi"><div class="label">총 검사</div><div class="value" id="k-total">-</div></div>
    <div class="card kpi"><div class="label">정상</div><div class="value" id="k-ok" style="color:var(--ok)">-</div></div>
    <div class="card kpi"><div class="label">불량</div><div class="value" id="k-def" style="color:var(--def)">-</div></div>
    <div class="card kpi"><div class="label">불량률</div><div class="value" id="k-rate">-</div></div>
    <div class="card kpi"><div class="label">재검사 필요 (AI 확신도 낮음)</div><div class="value" id="k-review" style="color:#d97706">-</div></div>
  </section>

  <section class="charts">
    <div class="card"><h2>판정 결과 비율</h2><div class="chart-box"><canvas id="c-result"></canvas></div></div>
    <div class="card"><h2>불량 유형별 건수</h2><div class="chart-box"><canvas id="c-type"></canvas></div></div>
    <div class="card"><h2>일별 검사 수 / 불량률</h2><div class="chart-box"><canvas id="c-daily"></canvas></div></div>
  </section>

  <section class="card" style="margin-top:12px">
    <h2>검사 이력</h2>
    <div class="toolbar">
      <select id="filter"><option value="">전체</option><option value="DEFECT">불량만</option><option value="OK">정상만</option><option value="REVIEW">재검사 필요</option></select>
      <button id="refresh">새로고침</button>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>검사 시각</th><th>검사 ID</th><th>이미지</th><th>결과</th><th>불량 유형</th><th>확신도</th><th>판정 근거</th></tr></thead>
        <tbody id="rows"><tr><td colspan="7">불러오는 중…</td></tr></tbody>
      </table>
    </div>
    <div class="error" id="error"></div>
  </section>
</main>

<script>
  // ▼ API Gateway 배포 후 Invoke URL로 교체 (또는 주소 뒤에 ?api=URL 붙여서 접속)
  const API_URL = new URLSearchParams(location.search).get("api")
    || "https://6qymgjfjw4.execute-api.ap-southeast-2.amazonaws.com/prod";

  const charts = {};
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

  function draw(id, config) {
    charts[id]?.destroy();
    charts[id] = new Chart(document.getElementById(id), config);
  }

  async function getJSON(path) {
    const res = await fetch(API_URL.replace(/\/$/, "") + path);
    if (!res.ok) throw new Error(`${path} → HTTP ${res.status}`);
    return res.json();
  }

  async function load() {
    document.getElementById("error").textContent = "";
    try {
      const filter = document.getElementById("filter").value;
      const [stats, items] = await Promise.all([
        getJSON("/stats"),
        getJSON("/inspections" + (filter === "REVIEW" ? "?review=PENDING" : filter ? `?result=${filter}` : "")),
      ]);

      document.getElementById("k-total").textContent = stats.total;
      document.getElementById("k-ok").textContent = stats.ok;
      document.getElementById("k-def").textContent = stats.defect;
      document.getElementById("k-rate").textContent = (stats.defectRate * 100).toFixed(1) + "%";
      document.getElementById("k-review").textContent = stats.review ?? 0;

      draw("c-result", { type: "doughnut",
        data: { labels: ["정상", "불량"], datasets: [{ data: [stats.ok, stats.defect], backgroundColor: ["#16a34a", "#dc2626"] }] },
        options: { maintainAspectRatio: false } });

      const types = Object.entries(stats.byType).sort((a, b) => b[1] - a[1]);
      draw("c-type", { type: "bar",
        data: { labels: types.map(t => t[0]), datasets: [{ label: "건수", data: types.map(t => t[1]), backgroundColor: "#f97316" }] },
        options: { maintainAspectRatio: false, indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { ticks: { precision: 0 } } } } });

      draw("c-daily", {
        data: { labels: stats.byDate.map(d => d.date), datasets: [
          { type: "bar", label: "검사 수", data: stats.byDate.map(d => d.total), backgroundColor: "#93c5fd", yAxisID: "y" },
          { type: "line", label: "불량률(%)", data: stats.byDate.map(d => +(d.defectRate * 100).toFixed(1)), borderColor: "#dc2626", yAxisID: "y1" } ] },
        options: { maintainAspectRatio: false, scales: {
          y: { beginAtZero: true, ticks: { precision: 0 } },
          y1: { position: "right", min: 0, max: 100, grid: { drawOnChartArea: false } } } } });

      document.getElementById("rows").innerHTML = items.length ? items.map(i => `
        <tr>
          <td>${esc(i.inspectedAt?.replace("T", " ").slice(0, 19))}</td>
          <td>${esc(i.inspectionId)}</td>
          <td>${esc(i.imageKey?.split("/").pop())}</td>
          <td><span class="badge ${esc(i.result)}">${esc(i.result)}</span>${i.reviewStatus === "PENDING" ? ' <span class="badge REVIEW">재검사</span>' : ""}</td>
          <td>${esc(i.defectType)}</td>
          <td>${esc(i.confidence)}</td>
          <td class="reason">${esc(i.reason)}</td>
        </tr>`).join("") : `<tr><td colspan="7">검사 이력이 없습니다.</td></tr>`;

      document.getElementById("updated").textContent = "마지막 갱신: " + new Date().toLocaleString("ko-KR");
    } catch (e) {
      document.getElementById("error").textContent = "데이터를 불러오지 못했습니다: " + e.message +
        "\nAPI_URL 설정과 API Gateway 배포, Lambda 응답의 CORS 헤더를 확인하세요.";
    }
  }

  document.getElementById("refresh").onclick = load;
  document.getElementById("filter").onchange = load;
  load();
  setInterval(load, 30000);  // 30초마다 자동 갱신

  // ===== 판정 결과 알림 팝업 =====
  function toast(item) {
    const review = item.reviewStatus === "PENDING";
    const kind = item.result === "DEFECT" ? "DEFECT" : review ? "REVIEW" : "OK";
    const title = kind === "DEFECT" ? "🔴 불량 감지" : kind === "REVIEW" ? "🟠 재검사 필요" : "🟢 정상 판정";
    const el = document.createElement("div");
    el.className = "toast " + kind;
    el.innerHTML = `<b>${title}</b>${esc(item.imageKey?.split("/").pop())}` +
      (kind === "OK" ? "" : ` · ${esc(item.defectType)}<br>${esc(item.reason)}`) +
      `<small>${esc(item.inspectedAt?.replace("T", " ").slice(0, 19))} · 클릭하면 닫힘</small>`;
    el.onclick = () => el.remove();
    document.getElementById("toasts").prepend(el);
    setTimeout(() => el.remove(), kind === "OK" ? 6000 : 15000);
    if (kind === "DEFECT") {
      const k = document.getElementById("k-def").parentElement;
      k.classList.remove("flash"); void k.offsetWidth; k.classList.add("flash");
    }
  }

  // 업로드한 샘플의 판정 결과가 DynamoDB에 저장될 때까지 조회 API를 2초 간격으로 확인 (최대 30초)
  async function waitForResult(imageKey, status) {
    for (let i = 0; i < 15; i++) {
      await new Promise(r => setTimeout(r, 2000));
      try {
        const items = await getJSON("/inspections");
        const hit = items.find(it => it.imageKey === imageKey);
        if (hit) {
          status.textContent = `✅ 판정 완료 (${(i + 1) * 2}초 이내): ${hit.result} · ${hit.defectType}`;
          toast(hit);
          load();
          return;
        }
      } catch (e) { /* 다음 시도에서 재확인 */ }
    }
    status.textContent = "판정 결과가 아직 없습니다. 잠시 후 새로고침해 주세요.";
  }

  // ===== 직접 테스트 (POST /demo → 샘플 업로드 → 판정 파이프라인) =====
  document.querySelectorAll(".demo-btn").forEach(btn => btn.addEventListener("click", async () => {
    const status = document.getElementById("demo-status");
    const btns = document.querySelectorAll(".demo-btn");
    btns.forEach(b => b.disabled = true);
    status.textContent = "샘플 업로드 중…";
    try {
      // text/plain 본문 → CORS preflight 없이 바로 호출되는 단순 요청
      const res = await fetch(API_URL + "/demo", {
        method: "POST",
        headers: { "Content-Type": "text/plain" },
        body: JSON.stringify({ kind: btn.dataset.kind }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || `HTTP ${res.status}`);
      status.textContent = `📤 ${data.sample} 업로드 완료 → AI 판정 중…`;
      await waitForResult(data.imageKey, status);
    } catch (e) {
      status.textContent = "요청 실패: " + e.message;
    } finally {
      btns.forEach(b => b.disabled = false);
    }
  }));
</script>
</body>
</html>
QLENS_EOF
systemctl enable --now nginx
