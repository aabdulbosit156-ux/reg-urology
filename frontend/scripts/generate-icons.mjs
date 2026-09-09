import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import pngToIco from "png-to-ico";
import sharp from "sharp";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.resolve(__dirname, "..", "public");
const sourceIcon = path.join(publicDir, "logo-ur-icon.svg");

const BRAND = { r: 127, g: 86, b: 217, alpha: 1 }; // --color-brand-600 (#7f56d9)
const WHITE = { r: 255, g: 255, b: 255, alpha: 1 };
const TRANSPARENT = { r: 0, g: 0, b: 0, alpha: 0 };

async function renderIcon(size, { background = TRANSPARENT, scale = 1 } = {}) {
    const innerSize = Math.max(1, Math.round(size * scale));
    const iconBuffer = await sharp(sourceIcon, { density: 384 })
        .resize(innerSize, innerSize, { fit: "contain", background: TRANSPARENT })
        .png()
        .toBuffer();

    return sharp({ create: { width: size, height: size, channels: 4, background } })
        .composite([{ input: iconBuffer, gravity: "center" }])
        .png()
        .toBuffer();
}

async function main() {
    await mkdir(publicDir, { recursive: true });

    await writeFile(path.join(publicDir, "favicon.svg"), await readFile(sourceIcon));

    const favicon16 = await renderIcon(16);
    const favicon32 = await renderIcon(32);
    const favicon48 = await renderIcon(48);
    await writeFile(path.join(publicDir, "favicon-16x16.png"), favicon16);
    await writeFile(path.join(publicDir, "favicon-32x32.png"), favicon32);
    await writeFile(path.join(publicDir, "favicon.ico"), await pngToIco([favicon16, favicon32, favicon48]));

    // iOS home screen icon: opaque background, padded (iOS applies its own rounding/mask).
    await writeFile(path.join(publicDir, "apple-touch-icon.png"), await renderIcon(180, { background: WHITE, scale: 0.78 }));

    // PWA manifest "any" purpose icons: opaque background, light padding.
    await writeFile(path.join(publicDir, "icon-192.png"), await renderIcon(192, { background: WHITE, scale: 0.82 }));
    await writeFile(path.join(publicDir, "icon-512.png"), await renderIcon(512, { background: WHITE, scale: 0.82 }));

    // PWA manifest "maskable" icon: brand background, icon kept inside the ~80% safe-zone circle.
    await writeFile(path.join(publicDir, "maskable-512.png"), await renderIcon(512, { background: BRAND, scale: 0.6 }));

    // Open Graph / Twitter link-preview image. No baked-in title text — social platforms
    // render og:title/og:description themselves, and SVG text rendering isn't reliably
    // available across environments (depends on system fontconfig).
    const ogIcon = await sharp(sourceIcon, { density: 384 })
        .resize(280, 280, { fit: "contain", background: TRANSPARENT })
        .png()
        .toBuffer();
    const ogImage = await sharp({ create: { width: 1200, height: 630, channels: 4, background: BRAND } })
        .composite([{ input: ogIcon, gravity: "center" }])
        .png()
        .toBuffer();
    await writeFile(path.join(publicDir, "og-image.png"), ogImage);

    console.log("Generated favicon, PWA, and preview assets in", publicDir);
}

main().catch((err) => {
    console.error(err);
    process.exitCode = 1;
});
