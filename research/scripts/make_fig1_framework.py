import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":8.5})
fig,ax=plt.subplots(figsize=(7.2,3.5)); ax.set_xlim(0,100); ax.set_ylim(0,50); ax.axis("off")
NAVY="#15305e"; ROSE="#b0413e"; GOLD="#c3922e"; GREY="#eef1f6"
def box(x,y,w,h,title,body,fc=GREY,ec=NAVY,tc=NAVY):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.4,rounding_size=1.5",fc=fc,ec=ec,lw=1.2))
    ax.text(x+w/2,y+h-3.2,title,ha="center",va="top",fontweight="bold",color=tc,fontsize=8.8)
    ax.text(x+w/2,y+h-8.5,body,ha="center",va="top",color="#1b2433",fontsize=7.4,linespacing=1.35)
def arr(x1,y1,x2,y2,c=NAVY):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle="-|>",mutation_scale=11,color=c,lw=1.3))
box(1,27,16,19,"Meal photo","RGB (+ optional\ncard or depth);\nEXIF removed")
box(22,27,18,19,"(1) Recognition","VLM / ViT:\ndish d (top-3)\n+ style s\n(home/rest./light)")
box(45,27,18,19,"(2) Portion","grams m̂ with\nrange [m_lo, m_hi]\nprior / card / depth")
box(68,27,31,19,"(3) Recipe-aware nutrients","Ê = m̂ · e(d,s) / 100\ninterval = m_lo·e_low … m_hi·e_high\n17 nutrients + GI/GL",fc="#f6e4e2",ec=ROSE,tc=ROSE)
arr(17.4,36.5,21.6,36.5); arr(40.4,36.5,44.6,36.5); arr(63.4,36.5,67.6,36.5)
box(60,2,39,19,"Arabic Recipe Composition Table","22 dishes × 3 variants · 53 ingredients\ne(d,s) = 100·Σ w·r·e_k / Y\n(raw weights, retention, cooked yield)",fc="#fbf4e6",ec=GOLD,tc="#8a5a00")
arr(80,21.4,83.5,26.6,GOLD)
box(1,2,50,19,"Validation and use (web application)","weighed plates (ArabFood-N) → MAPE, 95% CI,\nBland–Altman, interval coverage;\n24-h recall, food record, FFQ, supplements")
arr(68.4,27.5,51.6,19.5,"#5c6678")
ax.text(50,49.5,"Hidden fat (oil, ghee, tahini, fatty meat) enters through the recipe, not the pixels",ha="center",va="top",fontsize=8,style="italic",color=ROSE)
fig.tight_layout(); fig.savefig("fig1_framework.png",dpi=300); fig.savefig("fig1_framework.pdf")
