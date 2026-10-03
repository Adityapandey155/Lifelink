(function () {
  const canvas = document.getElementById("bg-canvas");
  if (!canvas) { console.error("LifeLink: #bg-canvas not found in DOM"); return; }
  const ctx = canvas.getContext("2d");
  let w, h, particles, ekgOffset = 0;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  }
  window.addEventListener("resize", resize);
  resize();

  function makeParticles(count) {
    return Array.from({ length: count }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: 2 + Math.random() * 4.5,
      speed: 0.25 + Math.random() * 0.6,
      drift: (Math.random() - 0.5) * 0.5,
      alpha: 0.25 + Math.random() * 0.4,   // <-- much brighter now
    }));
  }
  particles = makeParticles(Math.min(90, Math.floor((window.innerWidth * window.innerHeight) / 14000)));

  function drawParticles() {
    for (const p of particles) {
      ctx.beginPath();
      const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 6);
      grad.addColorStop(0, `rgba(255,45,85,${p.alpha})`);
      grad.addColorStop(1, "rgba(255,45,85,0)");
      ctx.fillStyle = grad;
      ctx.arc(p.x, p.y, p.r * 6, 0, Math.PI * 2);
      ctx.fill();

      p.y -= p.speed;
      p.x += p.drift;
      if (p.y < -20) { p.y = h + 20; p.x = Math.random() * w; }
      if (p.x < -20) p.x = w + 20;
      if (p.x > w + 20) p.x = -20;
    }
  }

  function drawEKG() {
    ctx.save();
    ctx.globalAlpha = 0.28;               // <-- much brighter now
    ctx.strokeStyle = "#ff2d55";
    ctx.lineWidth = 2;
    ctx.shadowColor = "#ff2d55";
    ctx.shadowBlur = 12;
    ctx.beginPath();
    const baseY = h * 0.55;
    const step = 4;
    for (let x = 0; x < w; x += step) {
      const t = (x + ekgOffset) % 240;
      let y = baseY;
      if (t > 100 && t < 112) y = baseY - (t - 100) * 6;
      else if (t >= 112 && t < 118) y = baseY - 72 + (t - 112) * 14;
      else if (t >= 118 && t < 130) y = baseY + (130 - t) * 1.5;
      if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();
    ekgOffset += 1.8;
  }

  let running = true;
  document.addEventListener("visibilitychange", () => { running = !document.hidden; });

  function loop() {
    if (running && !reduceMotion) {
      ctx.clearRect(0, 0, w, h);
      drawEKG();
      drawParticles();
    } else if (running && reduceMotion) {
      ctx.clearRect(0, 0, w, h);
    }
    requestAnimationFrame(loop);
  }
  loop();

  console.log("LifeLink background animation initialized ✅");
})();