(function () {
  const STORAGE_KEY = "canvasforge-mobile-pair";

  const pairPanel = document.getElementById("pair-panel");
  const capturePanel = document.getElementById("capture-panel");
  const pairCode = document.getElementById("pair-code");
  const startPair = document.getElementById("start-pair");
  const sasBox = document.getElementById("sas-box");
  const sasCode = document.getElementById("sas-code");
  const confirmPair = document.getElementById("confirm-pair");
  const pairStatus = document.getElementById("pair-status");
  const uploadStatus = document.getElementById("upload-status");
  const fileInput = document.getElementById("file-input");
  const cameraInput = document.getElementById("camera-input");
  const unpairBtn = document.getElementById("unpair");

  let pendingToken = "";
  let pendingBase = "";

  function loadSession() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    } catch (err) {
      return null;
    }
  }

  function saveSession(session) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  }

  function clearSession() {
    localStorage.removeItem(STORAGE_KEY);
  }

  function showPaired() {
    pairPanel.classList.add("hidden");
    capturePanel.classList.remove("hidden");
  }

  function showPairing() {
    pairPanel.classList.remove("hidden");
    capturePanel.classList.add("hidden");
  }

  function parsePastedCode(raw) {
    const text = (raw || "").trim();
    if (!text) {
      throw new Error("Enter a pairing code");
    }
    if (text.startsWith("http://") || text.startsWith("https://")) {
      const url = new URL(text);
      const token = url.searchParams.get("pair");
      if (!token) {
        throw new Error("That link is missing a pair token");
      }
      return { base: url.origin, token: token };
    }
    if (text.includes("#")) {
      const parts = text.split("#");
      const hostport = parts[0];
      const token = parts.slice(1).join("#");
      return { base: "http://" + hostport, token: token };
    }
    throw new Error("Use the QR link or host:port#token");
  }

  async function fetchOffer(base, token) {
    const response = await fetch(base + "/api/pair/offer?token=" + encodeURIComponent(token));
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Desktop is not waiting to pair");
    }
    return data;
  }

  async function beginFromCode(raw) {
    const parsed = parsePastedCode(raw);
    pendingBase = parsed.base;
    pendingToken = parsed.token;
    const offer = await fetchOffer(pendingBase, pendingToken);
    sasCode.textContent = offer.security_code;
    sasBox.classList.remove("hidden");
    pairStatus.textContent = "Check the same code on the desktop, then confirm both sides.";
  }

  async function confirmOnPhone() {
    pairStatus.textContent = "Confirming…";
    const response = await fetch(pendingBase + "/api/pair/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: pendingToken, name: navigator.userAgent.slice(0, 80) }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Could not confirm pairing");
    }
    if (data.state === "paired" && data.device_token) {
      saveSession({ base: pendingBase, device_token: data.device_token });
      showPaired();
      uploadStatus.textContent = "Paired. This phone can send grabs without scanning again.";
      return;
    }
    pairStatus.textContent = "Waiting for the desktop to confirm the same security code…";
    pollUntilPaired();
  }

  async function pollUntilPaired() {
    for (let i = 0; i < 60; i += 1) {
      const response = await fetch(
        pendingBase + "/api/pair/status?token=" + encodeURIComponent(pendingToken)
      );
      const data = await response.json();
      if (data.state === "paired" && data.device_token) {
        saveSession({ base: pendingBase, device_token: data.device_token });
        showPaired();
        uploadStatus.textContent = "Paired. This phone can send grabs without scanning again.";
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    pairStatus.textContent = "Still waiting for the desktop to confirm.";
  }

  async function uploadFile(file) {
    const session = loadSession();
    if (!session) {
      throw new Error("This phone is not paired");
    }
    uploadStatus.textContent = "Sending " + file.name + "…";
    const buffer = await file.arrayBuffer();
    const response = await fetch(session.base + "/api/upload", {
      method: "POST",
      headers: {
        Authorization: "Bearer " + session.device_token,
        "Content-Type": file.type || "application/octet-stream",
        "X-Filename": file.name || "mobile-grab",
      },
      body: buffer,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Upload failed");
    }
    uploadStatus.textContent = "Saved on desktop as " + data.name;
  }

  startPair.addEventListener("click", async () => {
    try {
      await beginFromCode(pairCode.value);
    } catch (err) {
      pairStatus.textContent = err.message;
      sasBox.classList.remove("hidden");
    }
  });

  confirmPair.addEventListener("click", async () => {
    try {
      await confirmOnPhone();
    } catch (err) {
      pairStatus.textContent = err.message;
    }
  });

  fileInput.addEventListener("change", async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) {
      return;
    }
    try {
      await uploadFile(file);
    } catch (err) {
      uploadStatus.textContent = err.message;
    }
  });

  cameraInput.addEventListener("change", async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) {
      return;
    }
    try {
      await uploadFile(file);
    } catch (err) {
      uploadStatus.textContent = err.message;
    }
  });

  unpairBtn.addEventListener("click", () => {
    clearSession();
    showPairing();
    pairStatus.textContent = "This phone forgot the desktop. Pair again from Settings → Mobile.";
  });

  const params = new URLSearchParams(window.location.search);
  const qrToken = params.get("pair");
  if (qrToken) {
    pairCode.value = window.location.origin + "/?pair=" + qrToken;
    beginFromCode(pairCode.value).catch((err) => {
      pairStatus.textContent = err.message;
      sasBox.classList.remove("hidden");
    });
  } else if (loadSession()) {
    showPaired();
  }
})();
