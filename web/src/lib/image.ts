export type ResizedImage = { base64: string; dataUrl: string }

/**
 * Downscales an image file to a JPEG data URL with its longest edge
 * capped, so a meal photo upload stays a couple hundred KB and vision
 * cost stays predictable. Modern Chrome applies EXIF orientation when an
 * image is drawn to canvas, so no manual rotation handling is needed.
 */
export function resizeImage(file: File, maxEdge = 1024, quality = 0.8): Promise<ResizedImage> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file)
    const img = new Image()

    img.onload = () => {
      const scale = Math.min(1, maxEdge / Math.max(img.width, img.height))
      const canvas = document.createElement('canvas')
      canvas.width = Math.round(img.width * scale)
      canvas.height = Math.round(img.height * scale)

      const ctx = canvas.getContext('2d')
      URL.revokeObjectURL(objectUrl)
      if (!ctx) {
        reject(new Error('Canvas not supported.'))
        return
      }

      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
      const dataUrl = canvas.toDataURL('image/jpeg', quality)
      resolve({ base64: dataUrl.split(',')[1], dataUrl })
    }

    img.onerror = () => {
      URL.revokeObjectURL(objectUrl)
      reject(new Error('Could not read image.'))
    }

    img.src = objectUrl
  })
}
