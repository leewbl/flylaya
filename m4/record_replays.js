// FlyLaya M4: batch-record replay videos via the replay page (MediaRecorder).
// Load in eval:  %load /tmp/flylaya/m4/record_replays.js  then  await recordAll()
// Requires hub static server :8940 and run files in /tmp/flylaya/m4/runs/.
// Records 10x A_full + first N seeds of each ablation (5 min wall per 5 min run).

const fs = await import("node:fs");

function recordList() {
  const files = fs.readdirSync("/tmp/flylaya/m4/runs").filter(f => f.endsWith(".jsonl")).sort();
  const pick = (cfg, n) => files.filter(f => f.startsWith(cfg)).slice(0, n);
  return [...pick("A_full", 10),
          ...pick("B_no_laya", 2),
          ...pick("C_no_connectome", 2),
          ...pick("D_random_intent", 2)];
}

async function recordAll() {
  fs.mkdirSync("/tmp/flylaya/m4/replays", { recursive: true });
  const list = recordList();
  console.log("recording", list.length, "replays:", list.join(", "));
  const tab = await browser.open({
    name: "flylaya-recorder", url: "http://127.0.0.1:8940/replay/",
    viewport: { width: 1100, height: 720 }, downloads: "flylaya_replays_dl", timeout: 60000,
  });
  await tab.waitForSelector("#cv", { timeout: 20000 });
  for (const file of list) {
    await tab.run(async ({ page }, p) => {
      const input = await page.$("#file");
      await input.uploadFile(p);
      await new Promise(r => setTimeout(r, 2000));
    }, { args: [`/tmp/flylaya/m4/runs/${file}`] });
    await tab.run(async ({ page }) => { await page.click("#rec"); });  // start recording+playback
    await tab.run(async ({ page }) => {
      await page.waitForFunction(() => {
        const m = document.querySelector("#hud")?.textContent?.match(/frame (\d+)\/(\d+)/);
        return m && m[1] === m[2] && parseInt(m[1]) > 100;  // reached last frame
      }, { timeout: 340000, polling: 5000 });
    });
    await tab.run(async ({ page }) => { await page.click("#rec"); });  // stop & auto-download
    await new Promise(r => setTimeout(r, 5000));                       // download flush
    console.log("recorded", file, `(${new Date().toISOString()})`);
  }
  await tab.close();
  return { recorded: list.length };
}

globalThis.recordAll = recordAll;
"record_replays.js loaded; call await recordAll()";
