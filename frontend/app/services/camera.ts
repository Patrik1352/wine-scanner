/** Owns a single stream; late permission grants are stopped after close(). */
export class CameraSession {
  private generation = 0
  private stream: MediaStream | null = null
  async open(video: HTMLVideoElement): Promise<boolean> {
    this.close()
    const id = this.generation
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false })
    if (id !== this.generation) { stream.getTracks().forEach(t => t.stop()); return false }
    this.stream = stream
    video.srcObject = stream
    await video.play()
    return id === this.generation
  }
  close() { this.generation++; this.stream?.getTracks().forEach(t => t.stop()); this.stream = null }
  async capture(video: HTMLVideoElement): Promise<File | null> {
    if (!video.videoWidth || !this.stream) return null
    const id = this.generation
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth; canvas.height = video.videoHeight
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Не удалось сохранить кадр. Попробуйте ещё раз.')
    context.drawImage(video, 0, 0)
    const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/jpeg', .92))
    if (id !== this.generation) return null
    if (!blob) throw new Error('Не удалось сохранить кадр. Попробуйте ещё раз.')
    return new File([blob], 'camera.jpg', { type: 'image/jpeg' })
  }
}
