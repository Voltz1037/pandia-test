from pathlib import Path
import sys
p = Path(sys.argv[1])
w = int(sys.argv[2]); h = int(sys.argv[3])
b = p.read_bytes()
print('bytes', len(b))
y = b[:w*h]
u = b[w*h:w*h + (w//2)*(h//2)]
def mad_at(data, row_bytes, rows, step):
    rows = min(rows, len(data)//step)
    total = 0
    count = 0
    for r in range(rows-1):
        a = r*step
        c = (r+1)*step
        for x in range(row_bytes):
            total += abs(data[a+x]-data[c+x])
            count += 1
    return total/count if count else -1
print('Y_mad_960', round(mad_at(y,w,h,w),6))
print('Y_mad_1024', round(mad_at(y,w,h,1024),6))
print('U_mad_480', round(mad_at(u,w//2,h//2,w//2),6))
print('U_mad_512', round(mad_at(u,w//2,h//2,512),6))
