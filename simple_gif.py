import struct

class GIFEncoder:
    """
    A minimal GIF89a encoder in pure Python.
    Supports basic animation, global color table (256 colors), and LZW compression (simplified or uncompressed).
    
    For simplicity and speed in a "No Dependency" environment:
    - We will use 256 color quantization (simple or naive).
    - We will use uncompressed blocks or a very simple LZW if needed (uncompressed is allowed in GIF but larger).
      Actually, uncompressed GIF blocks are non-standard essentially but 'Clear Code' spam works sometimes.
      However, implementing a basic LZW is standard.
    """
    def __init__(self, width, height, loop=0):
        self.width = width
        self.height = height
        self.loop = loop
        self.data = bytearray()
        self.palette = []
        self.frames = []
        
    def start(self):
        # Header GIF89a
        self.data.extend(b'GIF89a')
        # Logical Screen Descriptor
        self.data.extend(struct.pack('<HH', self.width, self.height))
        
        # Packed Fields
        # 1   : Global Color Table Flag (1 = Yes)
        # 111 : Color Resolution (8 bits - 1)
        # 0   : Sort Flag
        # 111 : Size of Global Color Table (2^(7+1) = 256)
        # Binary: 1 111 0 111 = 0xF7
        self.data.append(0xF7)
        
        # Background Color Index (0)
        self.data.append(0)
        # Pixel Aspect Ratio (0 = No aspect info)
        self.data.append(0)
        
        # Global Color Table placeholder (will be filled at finish or assumed fixed?)
        # For better quality, we usually use a palette per frame (Local Color Table) or Global.
        # To keep it simple, let's use a standard Web Safe palette or a fixed Quantization.
        # Or even better: Compute a palette from the first frame?
        # Let's start with a fixed standard 6-6-6 web palette + grays to ensure we don't have to quantize perfectly.
        self.palette = self._generate_palette()
        for r, g, b in self.palette:
            self.data.extend((r, g, b))
        # Fill rest to 256
        for _ in range(256 - len(self.palette)):
            self.data.extend((0, 0, 0))
            
        # Netscape Application Extension for Looping
        if self.loop >= 0:
            self.data.extend(b'\x21\xFF\x0BNETSCAPE2.0')
            self.data.extend(b'\x03\x01')
            self.data.extend(struct.pack('<H', self.loop)) # Loop count
            self.data.append(0)

    def add_frame(self, pixels, width, height, delay=10, is_bgra=False):
        """
        pixels: list of (r,g,b) tuples or flat list or bytes.
        delay: in 1/100ths of a second.
        is_bgra: if True, input is BGRA (e.g. from BMP or Windows)
        """
        # Graphics Control Extension
        self.data.append(0x21)
        self.data.append(0xF9)
        self.data.append(4)
        self.data.append(0x08 | 0x00) # Disposal 2
        self.data.extend(struct.pack('<H', delay))
        self.data.append(0)
        self.data.append(0)
        
        # Image Descriptor
        self.data.append(0x2C)
        self.data.extend(struct.pack('<HH', 0, 0))
        self.data.extend(struct.pack('<HH', width, height))
        self.data.append(0x00)
        
        self.data.append(8) # Min Code Size
        
        # Optimization: Use Numpy if available
        indices = self._map_pixels_to_palette_numpy(pixels, is_bgra)
        if indices is None:
             indices = self._map_pixels_to_palette(pixels, is_bgra)
             
        lzw_data = self._lzw_encode(indices)
        
        for i in range(0, len(lzw_data), 255):
            chunk = lzw_data[i:i+255]
            self.data.append(len(chunk))
            self.data.extend(chunk)
            
        self.data.append(0)

    def _map_pixels_to_palette_numpy(self, pixels, is_bgra):
        try:
            import numpy as np
            # Buffer to array
            # Assume pixels is bytes
            arr = np.frombuffer(pixels, dtype=np.uint8)
            
            # Reshape to (N, 4)
            # Check length perfect multiple
            if len(arr) % 4 != 0: return None
            arr = arr.reshape(-1, 4)
            
            # Extract RGB
            if is_bgra:
                r = arr[:, 2]
                g = arr[:, 1]
                b = arr[:, 0]
            else:
                r = arr[:, 0]
                g = arr[:, 1]
                b = arr[:, 2]
            
            # Vectorized level calculation (6x6x6 web safe)
            # Function: 0 if <26, 1 if <77 ...
            # np.searchsorted can map
            
            # Levels thresholds: 26, 77, 128, 179, 230
            thresholds = np.array([26, 77, 128, 179, 230])
            
            r_lvl = np.searchsorted(thresholds, r)
            g_lvl = np.searchsorted(thresholds, g)
            b_lvl = np.searchsorted(thresholds, b)
            
            # index = r*36 + g*6 + b
            indices = r_lvl * 36 + g_lvl * 6 + b_lvl
            return indices.tolist()
            
        except ImportError:
            return None
        except Exception as e:
            print(f"Numpy Error: {e}")
            return None

    def _map_pixels_to_palette(self, pixels, is_bgra=False):
        indices = []
        
        def get_level(v):
            if v < 26: return 0
            if v < 77: return 1
            if v < 128: return 2
            if v < 179: return 3
            if v < 230: return 4
            return 5
            
        step = 4
        # Offset map
        # If RGBA: r=0, g=1, b=2
        # If BGRA: r=2, g=1, b=0
        
        ro, go, bo = (0, 1, 2)
        if is_bgra: ro, go, bo = (2, 1, 0)
        
        for i in range(0, len(pixels), 4):
            r = pixels[i+ro]
            g = pixels[i+go]
            b = pixels[i+bo]
            
            li = get_level(r)*36 + get_level(g)*6 + get_level(b)
            indices.append(li)
            
        return indices

    def finish(self, filepath):
        self.data.append(0x3B) # Trailer
        with open(filepath, 'wb') as f:
            f.write(self.data)

    def _generate_palette(self):
        # 6x6x6 Color Cube (216 colors)
        pal = []
        levels = [0, 51, 102, 153, 204, 255]
        for r in levels:
            for g in levels:
                for b in levels:
                    pal.append((r, g, b))
        return pal

    def _map_pixels_to_palette(self, pixels):
        # Simple Euclidean mapping to 6x6x6 cube
        # Optimization: Map directly by integer math without search
        indices = []
        
        # pixels might be flat list from get_screen_region?
        # get_screen_region returns RGBA bytes 32bpp.
        # Format is R,G,B,A, R,G,B,A...
        
        # Pre-calc map
        # r (0-255) -> level (0-5)
        # index = r_lvl*36 + g_lvl*6 + b_lvl
        
        def get_level(v):
            if v < 26: return 0
            if v < 77: return 1
            if v < 128: return 2
            if v < 179: return 3
            if v < 230: return 4
            return 5
            
        for i in range(0, len(pixels), 4):
            # Assuming bytes
            r = pixels[i]
            g = pixels[i+1]
            b = pixels[i+2]
            # alpha ignored
            
            li = get_level(r)*36 + get_level(g)*6 + get_level(b)
            indices.append(li)
            
        return indices

    def _lzw_encode(self, indices):
        # Basic LZW
        code_size = 8 + 1
        next_code = 258 # 256=Clear, 257=End
        table = {bytes([i]): i for i in range(256)}
        clear_code = 256
        end_code = 257
        
        output = bytearray()
        
        # Bit packing state
        out_bits = []
        
        def emit(code):
            # Write code in current code_size bits
            # to output stream
            # We accumulate bits and write bytes ?
            # GIF LZW packs LSB first.
            nonlocal code_size
            curr = code
            for _ in range(code_size):
                 out_bits.append(curr & 1)
                 curr >>= 1
                 
        emit(clear_code)
        
        pattern = bytes()
        for idx in indices:
            c = bytes([idx])
            new_pattern = pattern + c
            if new_pattern in table:
                pattern = new_pattern
            else:
                emit(table[pattern])
                table[new_pattern] = next_code
                next_code += 1
                pattern = c
                
                if next_code == (1 << code_size):
                     code_size += 1
                if next_code == 4096:
                     emit(clear_code)
                     table = {bytes([i]): i for i in range(256)}
                     code_size = 8 + 1
                     next_code = 258
                     
        emit(table[pattern])
        emit(end_code)
        
        # Convert bits to bytes
        res = bytearray()
        while len(out_bits) >= 8:
            byte_val = 0
            for i in range(8):
                if out_bits[i]: byte_val |= (1 << i)
            res.append(byte_val)
            out_bits = out_bits[8:]
        
        if out_bits:
            byte_val = 0
            for i in range(len(out_bits)):
                if out_bits[i]: byte_val |= (1 << i)
            res.append(byte_val)
            
        return res
