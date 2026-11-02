typedef struct {
    short type;
    char pad[148];
    char b96;
} S0006BEE0;

int func_0006BEE0(S0006BEE0 *p)
{
    if ((p->type == 0 || (p->type >= 14 && p->type <= 20)
         || (p->type >= 22 && p->type <= 24) || p->type == 27)
        && p->b96 != 2) {
        return 1;
    }
    return 0;
}
