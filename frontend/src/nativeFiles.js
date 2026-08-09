import { isNativeApp } from './apiBase';

/**
 * Getting a file out of the app.
 *
 * WHY THE BUTTONS DID NOTHING IN THE APK
 * --------------------------------------
 * Both Download PDF and Share were written for a browser, and the Android
 * WebView is not one. Two separate holes, both silent:
 *
 *   1. `<a download>` is not implemented in the Android WebView. Creating the
 *      anchor, clicking it and revoking the object URL all "succeeded" - no
 *      exception, no file. The code then set the status to "Downloaded", so
 *      the app cheerfully reported success for something that never happened.
 *
 *   2. The Web Share API is not implemented in the Android WebView either.
 *      `navigator.canShare` is undefined, so the share button fell through to
 *      the download branch above - which is the hole in (1) - and displayed
 *      "Downloaded — sharing needs a phone" while running ON a phone.
 *
 * The native equivalents are Capacitor's Filesystem and Share plugins. The
 * file has to reach the disk before Android will share it: an intent carries a
 * URI, not bytes, so there is no way to hand the share sheet a blob.
 *
 * The browser path is unchanged. Every function here checks which shell it is
 * in first, so nothing about the website is affected.
 */

/**
 * Blob to base64, without the data URL prefix.
 *
 * Capacitor moves file contents across the JS/native bridge as a string, so a
 * binary PDF has to be encoded. FileReader rather than a manual byte loop:
 * a 200KB PDF is ~200,000 iterations of String.fromCharCode on the UI thread,
 * which visibly stutters on a cheap phone.
 */
export function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Could not read the file.'));
    reader.onload = () => {
      const result = String(reader.result || '');
      const comma = result.indexOf(',');
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.readAsDataURL(blob);
  });
}

/** The browser way: an anchor click. Works everywhere except a WebView. */
function browserDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Deferred: revoking synchronously can cancel the download in Firefox
  // before it has read the blob.
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

/** Write to one Capacitor directory, returning the file URI. */
async function writeTo(blob, filename, which) {
  const { Filesystem, Directory } = await import('@capacitor/filesystem');
  const data = await blobToBase64(blob);
  const { uri } = await Filesystem.writeFile({
    path: filename,
    data,
    directory: Directory[which],
    // Not `recursive`: these directories already exist, and asking to create
    // them is an extra permission-shaped failure for no gain.
  });
  return uri;
}

/**
 * Save a file, by whichever route this platform actually supports.
 *
 * Documents first, because that is what "download" means to a person and it is
 * the one place every file manager shows. It is not always writable: Android 10
 * needs legacy storage enabled, and a device can refuse for its own reasons.
 *
 * When it refuses, the fallback is the share sheet - NOT a quiet write to the
 * cache. Cache would let this report "saved" about a file the user cannot find
 * and the system may delete at any time, which is the same class of lie the
 * old browser-only code told. The share sheet has a "Save to Files" entry, so
 * the user still ends up with the PDF and knows where they put it.
 *
 * @returns {Promise<{native: boolean, where: string, viaShare?: boolean}>}
 */
export async function saveFile(blob, filename) {
  if (!isNativeApp()) {
    browserDownload(blob, filename);
    return { native: false, where: 'your downloads' };
  }

  try {
    await writeTo(blob, filename, 'Documents');
    return { native: true, where: 'Documents' };
  } catch {
    const { cancelled } = await shareFile(blob, filename, filename);
    return { native: true, where: 'wherever you chose', viaShare: true, cancelled };
  }
}

/**
 * Offer the file to the share sheet.
 *
 * On native this is the real Android chooser, so the PDF can go to WhatsApp,
 * Gmail, Drive or Files without this app implementing any of them. On the web
 * it uses the Web Share API where the browser has it, and falls back to a
 * download where it does not - which is honest, because a desktop browser
 * genuinely cannot share a file.
 *
 * @returns {Promise<{method: 'native'|'web'|'download', cancelled?: boolean}>}
 */
export async function shareFile(blob, filename, title) {
  if (isNativeApp()) {
    const { Share } = await import('@capacitor/share');
    // Cache, not Documents: this copy exists only so the intent has a URI to
    // point at. Writing every shared file into the user's Documents folder
    // would leave litter behind after each share.
    const { Filesystem, Directory } = await import('@capacitor/filesystem');
    const data = await blobToBase64(blob);
    const { uri } = await Filesystem.writeFile({
      path: filename,
      data,
      directory: Directory.Cache,
    });

    try {
      await Share.share({ title: title || filename, files: [uri] });
      return { method: 'native' };
    } catch (e) {
      // Dismissing the sheet is a rejection, not a failure. Android's wording
      // for it has changed between versions, so match loosely rather than on
      // one exact string.
      if (/cancel|abort|dismiss/i.test(String(e?.message || e))) {
        return { method: 'native', cancelled: true };
      }
      throw e;
    }
  }

  const file = new File([blob], filename, { type: blob.type || 'application/pdf' });
  if (navigator.canShare?.({ files: [file] })) {
    await navigator.share({ files: [file], title: title || filename });
    return { method: 'web' };
  }

  browserDownload(blob, filename);
  return { method: 'download' };
}
