// The backend rejects a photo over 2 MB *decoded*, so the check is on the raw
// file size rather than the base64 string, which is about a third larger.
export const MAX_PHOTO_BYTES = 2 * 1024 * 1024;

export class PhotoTooLarge extends Error {
  constructor(bytes) {
    super(
      `That photo is ${(bytes / 1024 / 1024).toFixed(1)} MB. The limit is 2 MB — choose a smaller one.`,
    );
    this.name = 'PhotoTooLarge';
    this.code = 'PhotoTooLarge';
  }
}

/** Resolves to the base64 body only, with the data: URL prefix stripped. */
export function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    if (!file) {
      resolve(null);
      return;
    }
    if (file.size > MAX_PHOTO_BYTES) {
      reject(new PhotoTooLarge(file.size));
      return;
    }
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('That file could not be read.'));
    reader.onload = () => {
      const result = String(reader.result);
      const comma = result.indexOf(',');
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.readAsDataURL(file);
  });
}
