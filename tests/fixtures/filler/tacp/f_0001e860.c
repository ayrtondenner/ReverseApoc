typedef struct {
    short type;
    char pad2[184];
    short x;
    short y;
    short z;
} Obj0001E860;

extern short D_000E4D6E;
extern int D_000E6BF8;
extern int D_000E6BFC;

void func_0001E860(Obj0001E860 *p, int *sx, int *sy)
{
    int x;
    int y;
    int z;

    x = p->x - p->y;
    y = (p->x + p->y) / 2;
    z = p->z;
    switch (p->type) {
    case 5:
        x -= 36;
        y -= 48;
        break;
    case 10:
        x -= 48;
        y -= 104;
        break;
    case 11:
        x -= 48;
        y -= 84;
        break;
    case 12:
        x -= 84;
        y -= 72;
        break;
    }
    y += D_000E4D6E * 40;
    *sx = x - D_000E6BF8;
    *sy = y - D_000E6BFC - z;
}
