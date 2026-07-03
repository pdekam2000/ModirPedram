'use strict';

const fs = require('fs');
const path = require('path');

const FILE_INPUT_SELECTORS = [
  'input[type="file"]',
  'input[type="file"][accept*="image"]',
  '[data-testid*="upload"] input[type="file"]',
  '[class*="drop"] input[type="file"]',
  '[class*="upload"] input[type="file"]',
];

const PREVIEW_SELECTORS = [
  'img[src*="blob"]',
  'img[src*="data:image"]',
  '.preview img',
  '[class*="preview"] img',
  '[data-testid*="preview"] img',
];

const DROP_ZONE_SELECTORS = [
  '[data-testid*="upload"]',
  '[class*="dropzone"]',
  '[class*="drop-zone"]',
  '[class*="Dropzone"]',
  '[class*="upload"]',
  'div[role="presentation"]',
];

async function sleep(page, ms) {
  await page.waitForTimeout(ms);
}

async function hasUploadPreview(page) {
  for (const selector of PREVIEW_SELECTORS) {
    const preview = await page.$(selector);
    if (preview) return true;
  }
  return false;
}

function mimeTypeForPath(imagePath) {
  const ext = path.extname(imagePath).toLowerCase();
  if (ext === '.png') return 'image/png';
  if (ext === '.jpg' || ext === '.jpeg') return 'image/jpeg';
  if (ext === '.webp') return 'image/webp';
  if (ext === '.gif') return 'image/gif';
  return 'image/png';
}

async function tryDirectFileInputs(page, imagePath) {
  for (const selector of FILE_INPUT_SELECTORS) {
    try {
      const inputs = await page.$$(selector);
      for (const input of inputs) {
        await input.setInputFiles(imagePath);
        await sleep(page, 1500);
        if (await hasUploadPreview(page)) return true;
      }
    } catch (_) {
      // try next selector
    }
  }

  try {
    await page.setInputFiles('input[type="file"]', imagePath);
    await sleep(page, 1500);
    if (await hasUploadPreview(page)) return true;
  } catch (_) {}

  return false;
}

async function tryInjectedFileInput(page, imagePath) {
  await page.evaluate(() => {
    const existing = document.getElementById('__runway_inject__');
    if (existing) existing.remove();

    const inp = document.createElement('input');
    inp.type = 'file';
    inp.id = '__runway_inject__';
    inp.accept = 'image/*';
    inp.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;z-index:99999';
    document.body.appendChild(inp);
  });

  const injected = await page.$('#__runway_inject__');
  if (!injected) return false;

  await injected.setInputFiles(imagePath);
  await sleep(page, 1000);

  await page.evaluate((zoneSelectors) => {
    const inp = document.getElementById('__runway_inject__');
    if (!inp || !inp.files || inp.files.length === 0) return;

    inp.dispatchEvent(new Event('input', { bubbles: true }));
    inp.dispatchEvent(new Event('change', { bubbles: true }));

    const dt = new DataTransfer();
    dt.items.add(inp.files[0]);

    const zones = new Set();
    for (const sel of zoneSelectors) {
      document.querySelectorAll(sel).forEach((el) => zones.add(el));
    }
    if (zones.size === 0) zones.add(document.body);

    for (const zone of zones) {
      const opts = { bubbles: true, cancelable: true, dataTransfer: dt };
      zone.dispatchEvent(new DragEvent('dragenter', opts));
      zone.dispatchEvent(new DragEvent('dragover', opts));
      zone.dispatchEvent(new DragEvent('drop', opts));
    }
  }, DROP_ZONE_SELECTORS);

  await sleep(page, 1500);
  return hasUploadPreview(page);
}

async function tryDragDropDispatch(page, imagePath) {
  const payload = {
    base64: fs.readFileSync(imagePath).toString('base64'),
    fileName: path.basename(imagePath),
    mime: mimeTypeForPath(imagePath),
  };

  for (const selector of DROP_ZONE_SELECTORS) {
    try {
      const locator = page.locator(selector).first();
      if ((await locator.count()) === 0) continue;

      const dataTransfer = await page.evaluateHandle(
        ({ base64, fileName, mime }) => {
          const binary = atob(base64);
          const bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
          const file = new File([bytes], fileName, { type: mime });
          const dt = new DataTransfer();
          dt.items.add(file);
          return dt;
        },
        payload,
      );

      await locator.dispatchEvent('dragenter', { dataTransfer });
      await locator.dispatchEvent('dragover', { dataTransfer });
      await locator.dispatchEvent('drop', { dataTransfer });
      await dataTransfer.dispose();

      await sleep(page, 2000);
      if (await hasUploadPreview(page)) return true;
    } catch (_) {
      // try next drop zone selector
    }
  }

  const dispatched = await page.evaluate(
    ({ base64, fileName, mime, zoneSelectors }) => {
      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
      const file = new File([bytes], fileName, { type: mime });
      const dt = new DataTransfer();
      dt.items.add(file);

      let targets = [];
      for (const sel of zoneSelectors) {
        targets.push(...document.querySelectorAll(sel));
      }
      if (targets.length === 0) {
        targets = [...document.querySelectorAll('div')].filter((el) => {
          const rect = el.getBoundingClientRect();
          return rect.width >= 240 && rect.height >= 120;
        });
      }
      if (targets.length === 0) targets = [document.body];

      const seen = new Set();
      let fired = false;
      for (const target of targets) {
        if (seen.has(target)) continue;
        seen.add(target);
        const opts = { bubbles: true, cancelable: true, dataTransfer: dt };
        target.dispatchEvent(new DragEvent('dragenter', opts));
        target.dispatchEvent(new DragEvent('dragover', opts));
        target.dispatchEvent(new DragEvent('drop', opts));
        fired = true;
      }
      return fired;
    },
    { ...payload, zoneSelectors: DROP_ZONE_SELECTORS },
  );

  if (!dispatched) return false;
  await sleep(page, 2000);
  return hasUploadPreview(page);
}

/**
 * Upload a reference image to Runway's image-to-video drop zone.
 * Tries: direct file inputs → injected hidden input → drag-and-drop dispatch.
 */
async function uploadImageToRunway(page, imagePath) {
  const resolved = path.resolve(imagePath);
  if (!fs.existsSync(resolved)) {
    throw new Error(`Image not found: ${resolved}`);
  }

  if (await tryDirectFileInputs(page, resolved)) return true;

  try {
    if (await tryInjectedFileInput(page, resolved)) return true;
  } catch (_) {}

  try {
    if (await tryDragDropDispatch(page, resolved)) return true;
  } catch (_) {}

  return false;
}

async function fillPrompt(page, prompt) {
  if (!prompt) return;

  const selectors = [
    'textarea[placeholder*="Describe" i]',
    'textarea',
    '[contenteditable="true"]',
    '[role="textbox"]',
  ];

  for (const selector of selectors) {
    try {
      const box = page.locator(selector).first();
      if ((await box.count()) === 0) continue;
      await box.click();
      await box.fill(prompt);
      return;
    } catch (_) {}
  }
}

async function clickGenerate(page) {
  const selectors = [
    page.getByRole('button', { name: /generate/i }),
    'button:has-text("Generate")',
    '[data-testid*="generate"]',
  ];

  for (const selector of selectors) {
    try {
      const target = typeof selector === 'string' ? page.locator(selector).first() : selector.first();
      if ((await target.count()) === 0) continue;
      await target.click();
      return true;
    } catch (_) {}
  }
  return false;
}

/**
 * Image-to-video flow: upload reference frame, enter prompt, click Generate.
 */
async function generateVideoFromImage(page, imagePath, prompt, options = {}) {
  const uploaded = await uploadImageToRunway(page, imagePath);
  if (!uploaded) {
    throw new Error(
      'Runway image upload failed (tried file input, injected input, and drag-and-drop)',
    );
  }

  await fillPrompt(page, prompt);

  if (options.waitAfterUploadMs) {
    await sleep(page, options.waitAfterUploadMs);
  }

  const clicked = await clickGenerate(page);
  if (!clicked) {
    throw new Error('Generate button not found after image upload');
  }

  return { ok: true, uploaded: true };
}

module.exports = {
  uploadImageToRunway,
  generateVideoFromImage,
  hasUploadPreview,
};
