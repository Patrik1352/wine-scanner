import { afterEach, expect, it, vi } from 'vitest'
import { CameraSession } from '../app/services/camera'
afterEach(() => vi.unstubAllGlobals())
function setup() {
  const stop = vi.fn()
  const stream = { getTracks: () => [{ stop }] } as unknown as MediaStream
  const getUserMedia = vi.fn().mockResolvedValue(stream)
  vi.stubGlobal('navigator', { mediaDevices: {getUserMedia} })
  const video = { play: vi.fn().mockResolvedValue(undefined), videoWidth: 1920, videoHeight: 1080, srcObject: null } as unknown as HTMLVideoElement
  return {stream, stop, getUserMedia, video}
}
it('captures a JPEG from the live video and releases the camera', async () => {
  const {video, stop, getUserMedia}=setup()
  const drawImage=vi.fn()
  const create=vi.spyOn(document,'createElement').mockReturnValue({getContext:()=>({drawImage}), toBlob:(callback:BlobCallback)=>callback(new Blob(['jpeg'],{type:'image/jpeg'})),width:0,height:0} as unknown as HTMLCanvasElement)
  const camera=new CameraSession()
  expect(await camera.open(video)).toBe(true)
  const file=await camera.capture(video)
  expect(file?.type).toBe('image/jpeg');expect(file?.size).toBe(4)
  expect(drawImage).toHaveBeenCalledWith(video,0,0)
  expect(getUserMedia.mock.calls[0]![0].audio).toBe(false)
  camera.close();expect(stop).toHaveBeenCalledOnce();create.mockRestore()
})
it('stops a late stream when user closes the camera permission dialog',async()=>{
  const {video,stream,stop,getUserMedia}=setup()
  let grant!: (s:MediaStream)=>void
  getUserMedia.mockImplementation(()=>new Promise(resolve=>grant=resolve))
  const camera=new CameraSession();const pending=camera.open(video);camera.close();grant(stream)
  expect(await pending).toBe(false);expect(stop).toHaveBeenCalledOnce();expect(video.play).not.toHaveBeenCalled()
})
it('propagates denied permission for an actionable UI error',async()=>{
  const {video,getUserMedia}=setup();getUserMedia.mockRejectedValue(new DOMException('denied','NotAllowedError'))
  await expect(new CameraSession().open(video)).rejects.toMatchObject({name:'NotAllowedError'})
})
