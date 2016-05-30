#!/usr/bin/python2

from builtins import int

# FIXME: ugly hack to work with both pillow and PIL
def img_to_bytes(img):
    if 'tobytes' in dir(img):
        return img.tobytes()
    return img.tostring()

try:
    import zbar

    def read_qr_codes(image):
        image = image.convert('L')
        width, height = image.size

        raw = img_to_bytes(image)
        zimg = zbar.Image(width, height, 'Y800', raw)

        scanner = zbar.ImageScanner()
        scanner.scan(zimg)

        return [ sym.data for sym in zimg if str(sym.type) == 'QRCODE' ]

except ImportError:
    from jnius import autoclass

    ZImage = autoclass('net.sourceforge.zbar.Image')
    ZImageScanner = autoclass('net.sourceforge.zbar.ImageScanner')
    ZSymbol = autoclass('net.sourceforge.zbar.Symbol')

    def read_qr_codes(image):
        image = image.convert('L')
        width, height = image.size

        raw = img_to_bytes(image)
        zimg = ZImage(width, height, 'Y800')
        zimg.setData(raw)

        scanner = ZImageScanner()
        if scanner.scanImage(zimg) == 0:
            return list()

        syms = list()
        it = zimg.getSymbols().iterator()
        while it.hasNext():
            sym = it.next()
            if sym.getType() == ZSymbol.QRCODE:
                syms.append(sym.getData())

        return syms

if __name__ == "__main__":
    import gettext
    gettext.install('rktool', './lang', True)

    import sys
    from PIL import Image

    if len(sys.argv) < 2:
        print("Usage: ./img_decode.py <image file>...")
        sys.exit(0)

    for fn in sys.argv[1:]:
        with Image.open(fn) as img:
            for qr in read_qr_codes(img):
                print(qr)
