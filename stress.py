"""Generate held-out stress requests from the catalogue and score the agent on them.

    python stress.py --seed 21 --n 1500 --out stress.jsonl
    python evaluate.py --agent agent.py --data stress.jsonl

Every request is built from a real catalogue product, so the target is known and
unique under the filters. Phrasing is drawn from pools that are wider than the
public dev set: English and Hindi number words, "1.5k" / "Rs." / "rupees" budgets,
category and colour synonyms, size forms ("2XL", "double XL", "32 waist", "UK 9"),
corrections ("oops", "wait, I meant") and late constraints ("oh, and in blue").
Different seeds give different sets. It is our own generator: it measures
robustness of the parser and the commit policy, not the organisers' hidden set.
"""
import json, random, sys, re
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import search
cat = search.load_catalogue()
import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument('--seed', type=int, default=7)
_ap.add_argument('--n', type=int, default=600)
_ap.add_argument('--out', default='stress.jsonl')
_args = _ap.parse_args()
rnd = random.Random(_args.seed)
N = _args.n
ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = {20:"twenty",30:"thirty",40:"forty",50:"fifty",60:"sixty",70:"seventy",80:"eighty",90:"ninety"}
HI = {1:"ek",2:"do",3:"teen",4:"chaar",5:"paanch",6:"chhe",7:"saat",8:"aath",9:"nau",10:"das",15:"pandrah",17:"satrah",20:"bees",25:"pachees"}
def eng_hundreds(n):  # n multiple of 100 < 10000
    th, h = divmod(n, 1000); h//=100
    def w(x): return ONES[x] if x<20 else TENS[x//10*10]+(" "+ONES[x%10] if x%10 else "")
    parts=[]
    if th: parts.append(w(th)+" thousand")
    if h: parts.append(w(h)+" hundred")
    return " ".join(parts)
def price_forms(v):
    f=[f"{v}", f"{v:,}", f"Rs. {v}", f"₹{v}", f"rs {v}", f"{v} rupees"]
    if v%100==0: f.append(eng_hundreds(v))
    if v%500==0 or v%1000==0: f.append(f"{v/1000:g}k")
    return f
def trig(v):
    return rnd.choice(["under","below","within","max","budget","not more than","less than","up to","upto"])
size_apparel={"XS":["XS","extra small"],"S":["S","small"],"M":["M","medium"],"L":["L","large"],"XL":["XL","extra large"],"XXL":["XXL","2XL","double XL"]}
CATSYN={"running shoes":["running shoes","runners","jogging shoes","running sneakers"],"sneakers":["sneakers","casual shoes","casual sneakers"],
"sandals":["sandals","slides","floaters"],"track pants":["track pants","trackpants","joggers"],"jackets":["jacket"],"shirts":["shirt"],"dresses":["dress"],
"kurtas":["kurta"],"hoodies":["hoodie","hooded sweatshirt","sweatshirt"],"t-shirts":["t-shirt","tshirt","tee","t shirt"],"jeans":["jeans","denims","pair of jeans"],
"backpacks":["backpack","rucksack","bag pack"],"caps":["cap"],"headphones":["headphones","headset","earphones"],"watches":["watch","wristwatch"],"wallets":["wallet"]}
COLSYN={"black":["black","kaala"],"white":["white","safed"],"red":["red","laal"],"blue":["blue","neela"],"green":["green","hara"],"yellow":["yellow","peela"],"pink":["pink","gulabi"],"brown":["brown","bhura"],"navy":["navy","navy blue"],"olive":["olive","olive green"],"grey":["grey","gray"],"gold":["gold","golden"]}
def size_forms(p):
    s=p["size"]
    if not s: return None
    if s in size_apparel: return [f"size {x}" if len(x)<=3 else x for x in size_apparel[s]]+[f"{x} size" for x in size_apparel[s] if len(x)<=3]
    if p["category"] in ("jeans","track pants"): return [f"size {s}",f"{s} waist",f"waist {s}"]
    return [f"size {s}",f"UK {s}",f"size {s} UK",f"{s} UK",f"size {ONES[int(s)]}" if int(s)<20 else f"size {s}"]
OPEN=["","hi, ","hey, ","show me ","I need ","I want ","looking for ","can you find me ","get me ","do you have any ","I'd like ","please find ","um, ","uh, "]
FLUFF=[""," please"," thanks"," for my brother"," for the gym"," as a gift"," if you have it"," for a wedding"," for office"," nothing too flashy"," need it this week"]
def other(vals,cur): 
    c=[v for v in vals if v!=cur]; return rnd.choice(c)
brands=sorted({p["brand"] for p in cat if p["brand"]})
cols=sorted({p["colour"] for p in cat})
def build(p, budget):
    fl={"category":p["category"],"colour":p["colour"],"size":p["size"],"brand":p["brand"],"max_price":budget}
    kind=rnd.choice(["plain"]*5+["correction"]*2+["late"]*2+["hindi"])
    br=p["brand"]; ct=rnd.choice(CATSYN[p["category"]]); cl=rnd.choice(COLSYN.get(p["colour"],[p["colour"]]))
    sf=size_forms(p); sz=rnd.choice(sf) if sf else None
    pf=rnd.choice(price_forms(budget)); tg=trig(budget)
    pr=f"{tg} {pf}"
    tags=[]
    if kind=="hindi":
        tags=["code_mixed"]
        if budget%100==0 and rnd.random()<.7:
            hv=budget//100
            hp = f"{HI[hv//10]} hazaar" if hv%10==0 and hv//10 in HI else (f"{HI[hv]} sau" if hv in HI else str(budget))
        else: hp=str(budget)
        parts=[cl,br,ct]+([sz] if sz else [])+[f"{hp} {rnd.choice(['tak','ke andar'])}"]
        rnd.shuffle(parts)
        text=rnd.choice(["mujhe ","mere liye ","bhaiya, dikhao ","kya aapke paas "])+" ".join(parts)+rnd.choice([" chahiye"," milega?"," dikhao na"," hai kya?"," please"])
        return text,fl,tags
    order=[("c",f"{cl}"),("b",f"{br}" if rnd.random()<.5 else f"from {br}"),("t",ct)]
    rnd.shuffle(order)
    core=" ".join(x for _,x in order)
    segs=[core]
    if sz: segs.append(sz)
    segs.append(pr)
    rnd.shuffle(segs)
    if kind=="correction":
        tags=["correction"]
        which=rnd.choice(["size","colour","brand"]) if sz else rnd.choice(["colour","brand"])
        cue=rnd.choice(["oops,","sorry, I mean","wait, I meant","no wait,","actually","make that"])
        if which=="colour":
            wrong=other([c for c in COLSYN if c!=p["colour"]],p["colour"]); segs[0]=segs[0].replace(cl,f"{COLSYN[wrong][0]} {cue} {cl}",1)
        elif which=="brand":
            wrong=other(brands,br); segs[0]=segs[0].replace(br,f"{wrong} {cue} {br}",1)
        else:
            for i,sg in enumerate(segs):
                if sg==sz:
                    wsz=rnd.choice([x for x in ["S","M","L","XL","XS"]]) if p["size"] in size_apparel else str(rnd.choice([7,8,9,10]))
                    if wsz==p["size"]: wsz="XS" if wsz!="XS" else "XL"
                    segs[i]=f"size {wsz}, {cue} {sz}"
    text=rnd.choice(OPEN)+", ".join(segs)
    if kind=="late":
        tags=["late_constraint"]
        # drop one field from main and add at the end
        late=rnd.choice(["colour","brand"]) 
        if late=="colour":
            text=text.replace(cl,"",1).replace("  "," ")+rnd.choice([", oh, and in ",". and in ",", also in ",", one more thing, in "])+cl
        else:
            text=text.replace(f"from {br}","").replace(br,"",1).replace("  "," ")+rnd.choice([", oh, and from ",". and from "," also brand "])+br
    text=text.strip().replace(" ,",",")
    text+=rnd.choice(FLUFF) if kind!="late" else rnd.choice(["","", " please"," thanks"])
    return text,fl,tags
out=[]; tries=0
while len(out)<N and tries<20000:
    tries+=1
    p=rnd.choice(cat)
    if not p["size"] and rnd.random()<0.85: continue
    budget=p["price"]
    # nice budget >= price
    step=rnd.choice([100,500,1000])
    budget=((p["price"]+step-1)//step)*step
    if budget==p["price"] and rnd.random()<.5: pass
    text,fl,tags=build(p,budget)
    f={k:(v if v else None) for k,v in fl.items()}
    f={k:v for k,v in f.items() if v is not None}
    hits=search.search("",f,10)
    if len(hits)!=1 or hits[0]["product_id"]!=p["product_id"]: continue
    words=text.split()
    out.append({"id":f"st-{len(out):04d}","text":text,"words":words,"filters":fl,"target":p["product_id"],"tags":tags})
with open(_args.out,'w') as fh:
    for o in out: fh.write(json.dumps(o,ensure_ascii=False)+"\n")
print(len(out))
