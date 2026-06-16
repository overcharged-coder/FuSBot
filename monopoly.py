import json, math, os, random, sqlite3, io
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

try:
    from PIL import Image, ImageDraw, ImageFont
    import hashlib
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

TILENAME: List[str] = []
PRICEBUY: List[int] = []
RENTPRICE: List[int] = []
RRPRICE: List[int] = []
MORTGAGEPRICE: List[int] = []
TENMORTGAGEPRICE: List[int] = []
HOUSEPRICE: List[int] = []
PROPGROUPS: Dict[str, List[int]] = {}
PROPCOLORS: List[str] = []
CCNAME: List[str] = []
CHANCENAME: List[str] = []

TILENAME[:] = [
    "GO","Mediterranean Avenue","Community Chest","Baltic Avenue","Income Tax",
    "Reading Railroad","Oriental Avenue","Chance","Vermont Avenue","Connecticut Avenue",
    "Jail","St. Charles Place","Electric Company","States Avenue","Virginia Avenue",
    "Pennsylvania Railroad","St. James Place","Community Chest","Tennessee Avenue","New York Avenue",
    "Free Parking","Kentucky Avenue","Chance","Indiana Avenue","Illinois Avenue",
    "B. & O. Railroad","Atlantic Avenue","Ventnor Avenue","Water Works","Marvin Gardens",
    "Go To Jail","Pacific Avenue","North Carolina Avenue","Community Chest","Pennsylvania Avenue",
    "Short Line","Chance","Park Place","Luxury Tax","Boardwalk"
]
PRICEBUY[:] = [0,60,0,60,0,200,100,0,100,120,0,140,150,140,160,200,180,0,180,200,0,220,0,220,240,200,260,260,150,280,0,300,300,0,320,200,0,350,0,400]
HOUSEPRICE[:] = [0,50,0,50,0,0,50,0,50,50,0,100,0,100,100,0,100,0,100,100,0,150,0,150,150,0,150,150,0,150,0,200,200,0,200,0,0,200,0,200]
RENTPRICE[:] = [
    -1,-1,-1,-1,-1,-1, 2,10,30,90,160,250, -1,-1,-1,-1,-1,-1, 4,20,60,180,320,450,
    -1,-1,-1,-1,-1,-1, -1,-1,-1,-1,-1,-1, 6,30,90,270,400,550, -1,-1,-1,-1,-1,-1,
    6,30,90,270,400,550, 8,40,100,300,450,600, -1,-1,-1,-1,-1,-1, 10,50,150,450,625,750,
    -1,-1,-1,-1,-1,-1, 10,50,150,450,625,750, 12,60,180,500,700,900, -1,-1,-1,-1,-1,-1,
    14,70,200,550,750,950, -1,-1,-1,-1,-1,-1, 14,70,200,550,750,950, 16,80,220,600,800,1000,
    -1,-1,-1,-1,-1,-1, 18,90,250,700,875,1050, -1,-1,-1,-1,-1,-1, 18,90,250,700,875,1050,
    -1,-1,-1,-1,-1,-1, 20,100,300,750,925,1100, 22,110,330,800,975,1150, -1,-1,-1,-1,-1,-1,
    22,110,330,800,975,1150, 24,120,360,850,1025,1200, -1,-1,-1,-1,-1,-1, 26,130,390,900,1100,1275,
    26,130,390,900,1100,1275, -1,-1,-1,-1,-1,-1, 28,150,450,1000,1200,1400,
    -1,-1,-1,-1,-1,-1, -1,-1,-1,-1,-1,-1, 35,175,500,1100,1300,1500, -1,-1,-1,-1,-1,-1,
    50,200,600,1400,1700,2000
]
RRPRICE[:] = [0,25,50,100,200]
MORTGAGEPRICE[:] = [0,30,0,30,0,100,50,0,50,60,0,70,75,70,80,100,90,0,90,100,0,110,0,110,120,100,130,130,75,140,0,150,150,0,160,100,0,175,0,200]
TENMORTGAGEPRICE[:] = [0,33,0,33,0,110,55,0,55,66,0,77,83,77,88,110,99,0,99,110,0,121,0,121,132,110,143,143,83,154,0,165,165,0,176,110,0,193,0,220]
PROPCOLORS[:] = ["","brown","","brown","","rr","lightblue","","lightblue","lightblue","","pink","utility","pink","pink","rr","orange","","orange","orange","","red","","red","red","rr","yellow","yellow","utility","yellow","","green","green","","green","rr","","darkblue","","darkblue"]
PROPGROUPS.update({"brown":[1,3],"lightblue":[6,8,9],"pink":[11,13,14],"orange":[16,18,19],"red":[21,23,24],"yellow":[26,27,29],"green":[31,32,34],"darkblue":[37,39]})
CCNAME[:] = ["Advance to GO","Bank error in your favor","Doctor's fees","Sale of stock","Get Out of Jail Free","Go to Jail","Grand Opera opening","Holiday fund matures","Income tax refund","Life insurance matures","Hospital fees","School fees","Consultancy fee","Street repairs","You have won second prize","You inherit $100","Birthday gifts"]
CHANCENAME[:] = ["Advance to GO","Advance to Illinois Avenue","Advance to St. Charles Place","Advance to nearest Utility","Advance to nearest Railroad","Bank pays you dividend","Get Out of Jail Free","Go back three spaces","Go to Jail","Street repairs","Pay poor tax","Take a ride on the Reading","Take a walk on Boardwalk","Chairman of the Board","Building loan matures","Crossword competition"]


@dataclass
class GameConfig:
    startCash: int = 1500; incomeValue: int = 200; luxuryValue: int = 100
    doAuction: bool = True; bailValue: int = 50; maxJailRolls: int = 3
    doDoubleGo: bool = False; goValue: int = 200; freeParkingValue: Optional[Union[int, str]] = None
    hotelLimit: int = 12; houseLimit: int = 32; minRaise: int = 1

@dataclass
class PlayerSlot:
    user_id: str; is_ai: bool = False; ai_name: str = "[AI]"; ai_profile: str = "normal"

@dataclass
class TurnSnapshot:
    p: int; was_doubles: bool; num_doubles: int; rolled: Optional[Tuple[int, int]] = None; last_move: int = 0

@dataclass
class MonopolyState:
    uid: List[PlayerSlot]; num: int; numalive: int; p: int = 0
    injail: List[bool] = field(default_factory=list); tile: List[int] = field(default_factory=list)
    bal: List[int] = field(default_factory=list); goojf: List[int] = field(default_factory=list)
    isalive: List[bool] = field(default_factory=list); jailturn: List[int] = field(default_factory=list)
    ownedby: List[int] = field(default_factory=list); numhouse: List[int] = field(default_factory=list)
    ismortgaged: List[int] = field(default_factory=list); freeparkingsum: int = 0
    ccn: int = 0; ccorder: List[int] = field(default_factory=list)
    chancen: int = 0; chanceorder: List[int] = field(default_factory=list)
    turn: TurnSnapshot = field(default_factory=lambda: TurnSnapshot(p=0, was_doubles=True, num_doubles=0))

    def to_json(self) -> str: d = asdict(self); return json.dumps(d)
    @classmethod
    def from_json(cls, s: str) -> "MonopolyState":
        d = json.loads(s); d["uid"] = [PlayerSlot(**u) for u in d["uid"]]; d["turn"] = TurnSnapshot(**d["turn"]); return cls(**d)


@dataclass
class EngineEvent:
    kind: str; data: Dict[str, Any] = field(default_factory=dict)


class MonopolyEngine:
    def __init__(self, state: MonopolyState, cfg: GameConfig, rng: Optional[random.Random] = None):
        self.s = state; self.cfg = cfg; self.rng = rng or random.Random(); self.events: List[EngineEvent] = []

    @staticmethod
    def new_game(player_slots: List[PlayerSlot], cfg: GameConfig, rng: Optional[random.Random] = None) -> "MonopolyEngine":
        n = len(player_slots)
        if n < 2 or n > 8: raise ValueError("Monopoly needs 2-8 players")
        r = rng or random.Random()
        ownedby = [-2,-1,-2,-1,-2,-1,-1,-2,-1,-1,-2,-1,-1,-1,-1,-1,-1,-2,-1,-1,-2,-1,-2,-1,-1,-1,-1,-1,-1,-1,-2,-1,-1,-2,-1,-1,-2,-1,-2,-1]
        numhouse = [-1,0,-1,0,-1,-1,0,-1,0,0,-1,0,-1,0,0,-1,0,-1,0,0,-1,0,-1,0,0,-1,0,0,-1,0,-1,0,0,-1,0,-1,-1,0,-1,0]
        ismortgaged = [-1,0,-1,0,-1,0,0,-1,0,0,-1,0,0,0,0,0,0,-1,0,0,-1,0,-1,0,0,0,0,0,0,0,-1,0,0,-1,0,0,-1,0,-1,0]
        ccorder = list(range(17)); chanceorder = list(range(16)); r.shuffle(ccorder); r.shuffle(chanceorder)
        s = MonopolyState(uid=player_slots, num=n, numalive=n, p=0, injail=[False]*n, tile=[0]*n, bal=[cfg.startCash]*n, goojf=[0]*n, isalive=[True]*n, jailturn=[-1]*n, ownedby=ownedby, numhouse=numhouse, ismortgaged=ismortgaged, freeparkingsum=0, ccn=0, ccorder=ccorder, chancen=0, chanceorder=chanceorder, turn=TurnSnapshot(p=0, was_doubles=True, num_doubles=0))
        return MonopolyEngine(s, cfg, rng=r)

    def clear_events(self): self.events.clear()
    def cur(self): return self.s.p
    def alive_players(self): return [i for i in range(self.s.num) if self.s.isalive[i]]

    def advance_to_next_player(self):
        n = self.s.num
        for _ in range(n):
            self.s.p = (self.s.p + 1) % n
            if self.s.isalive[self.s.p]:
                self.s.turn = TurnSnapshot(p=self.s.p, was_doubles=True, num_doubles=0); return
        self.s.turn = TurnSnapshot(p=self.s.p, was_doubles=False, num_doubles=0)

    def game_over(self): return self.s.numalive <= 1

    def winner(self):
        if self.s.numalive != 1: return None
        return next((i for i in range(self.s.num) if self.s.isalive[i]), None)

    def _add_event(self, kind, **data): self.events.append(EngineEvent(kind=kind, data=dict(data)))

    def _passed_go(self, pid, landed):
        add = self.cfg.goValue * (2 if (landed and self.cfg.doDoubleGo) else 1)
        self.s.bal[pid] += add; self._add_event("go_money", pid=pid, amount=add)

    def roll(self):
        d1 = self.rng.randint(1,6); d2 = self.rng.randint(1,6); self.s.turn.rolled = (d1,d2); return d1,d2

    def legal_actions(self):
        pid = self.cur()
        if not self.s.isalive[pid]: return []
        if self.s.bal[pid] < 0: return ["trade","house","mortgage","forfeit"]
        if self.s.injail[pid]:
            acts = ["bail"]
            if self.s.jailturn[pid] <= self.cfg.maxJailRolls: acts.append("roll")
            if self.s.goojf[pid] > 0: acts.append("use_goojf")
            return acts
        if self.s.turn.rolled is None: return ["roll","trade","house","mortgage"]
        return ["trade","house","mortgage","end"]

    def jail_roll(self):
        pid = self.cur()
        if not self.s.injail[pid]: raise RuntimeError("not in jail")
        if self.s.jailturn[pid] == -1: self.s.jailturn[pid] = 0
        self.s.jailturn[pid] += 1
        if self.s.jailturn[pid] > self.cfg.maxJailRolls: self._add_event("jail_forced_bail", pid=pid, bail=self.cfg.bailValue); return
        d1,d2 = self.roll(); self._add_event("rolled", pid=pid, d1=d1, d2=d2, total=d1+d2, doubles=(d1==d2))
        if d1 == d2: self.s.jailturn[pid] = -1; self.s.injail[pid] = False; self._add_event("jail_exit", pid=pid, method="doubles"); self.land(pid, d1+d2)

    def pay_bail_and_roll(self):
        pid = self.cur()
        self.s.bal[pid] -= self.cfg.bailValue; self.s.freeparkingsum += self.cfg.bailValue
        self.s.jailturn[pid] = -1; self.s.injail[pid] = False
        self._add_event("bail_paid", pid=pid, bail=self.cfg.bailValue, balance=self.s.bal[pid])
        d1,d2 = self.roll(); self._add_event("rolled", pid=pid, d1=d1, d2=d2, total=d1+d2, doubles=(d1==d2))
        if d1 == d2: self.s.turn.num_doubles += 1
        else: self.s.turn.was_doubles = False
        self.land(pid, d1+d2)

    def use_goojf_and_roll(self):
        pid = self.cur()
        if self.s.goojf[pid] <= 0: raise RuntimeError("no goojf")
        self.s.goojf[pid] -= 1; self.s.jailturn[pid] = -1; self.s.injail[pid] = False
        self._add_event("goojf_used", pid=pid, remaining=self.s.goojf[pid])
        d1,d2 = self.roll(); self._add_event("rolled", pid=pid, d1=d1, d2=d2, total=d1+d2, doubles=(d1==d2))
        if d1 == d2: self.s.turn.num_doubles += 1
        else: self.s.turn.was_doubles = False
        self.land(pid, d1+d2)

    def normal_roll(self):
        pid = self.cur()
        if self.s.injail[pid]: raise RuntimeError("in jail")
        d1,d2 = self.roll(); self._add_event("rolled", pid=pid, d1=d1, d2=d2, total=d1+d2, doubles=(d1==d2))
        if d1 == d2: self.s.turn.num_doubles += 1
        else: self.s.turn.was_doubles = False
        if self.s.turn.num_doubles >= 3:
            self.s.tile[pid] = 10; self.s.injail[pid] = True; self.s.turn.was_doubles = False
            self._add_event("go_to_jail", pid=pid, reason="three_doubles"); return
        self.land(pid, d1+d2)

    def land(self, pid, distance):
        prev = self.s.tile[pid]; new = prev + distance; passed = new >= 40
        if passed: new -= 40; self._passed_go(pid, landed=(new==0))
        self.s.tile[pid] = new; self.s.turn.last_move = distance
        self._add_event("moved", pid=pid, from_tile=prev, to_tile=new, distance=distance, passed_go=passed)
        self._resolve_tile(pid, distance)
        if self.s.bal[pid] < 0: self._add_event("debt", pid=pid, balance=self.s.bal[pid])

    def _resolve_tile(self, pid, distance):
        t = self.s.tile[pid]; self._add_event("landed", pid=pid, tile=t, name=TILENAME[t] if t < len(TILENAME) else str(t))
        owner = self.s.ownedby[t]
        if owner == pid: self._add_event("own_tile", pid=pid, tile=t); return
        if self.s.ismortgaged[t] == 1: self._add_event("mortgaged_no_rent", pid=pid, tile=t, owner=owner); return
        if owner == -2: self._resolve_unownable(pid, distance); return
        if owner == -1: self._add_event("buy_offer", pid=pid, tile=t, price=PRICEBUY[t], balance=self.s.bal[pid]); return
        if RENTPRICE[t*6] == -1: self._pay_rr_util(pid, owner, t, distance)
        else: self._pay_property_rent(pid, owner, t)

    def buy_current_tile(self):
        pid = self.cur(); t = self.s.tile[pid]
        if self.s.ownedby[t] != -1: raise RuntimeError("tile not buyable now")
        price = PRICEBUY[t]
        if self.s.bal[pid] < price: raise RuntimeError("cannot afford")
        self.s.bal[pid] -= price; self.s.ownedby[t] = pid; self._add_event("bought", pid=pid, tile=t, price=price, balance=self.s.bal[pid])

    def decline_buy_current_tile(self):
        pid = self.cur(); t = self.s.tile[pid]
        if self.s.ownedby[t] != -1: raise RuntimeError("tile not declinable now")
        self._add_event("buy_declined", pid=pid, tile=t, doAuction=self.cfg.doAuction)

    def _resolve_unownable(self, pid, distance):
        t = self.s.tile[pid]
        if t == 0: return
        if t == 10: self._add_event("jail_visiting", pid=pid); return
        if t == 20:
            v = self.cfg.freeParkingValue
            if v is None: return
            if v == "tax": amt = self.s.freeparkingsum; self.s.bal[pid] += amt; self._add_event("free_parking", pid=pid, amount=amt); self.s.freeparkingsum = 0; return
            if isinstance(v, int): self.s.bal[pid] += v; self._add_event("free_parking", pid=pid, amount=v); return
            return
        if t == 30: self.s.injail[pid] = True; self.s.tile[pid] = 10; self.s.turn.was_doubles = False; self._add_event("go_to_jail", pid=pid, reason="tile_30"); return
        if t in (2,17,33): self._community_chest(pid); return
        if t in (7,22,36): self._chance(pid, distance); return
        if t == 4: self.s.bal[pid] -= self.cfg.incomeValue; self.s.freeparkingsum += self.cfg.incomeValue; self._add_event("tax", pid=pid, kind="income", amount=self.cfg.incomeValue); return
        if t == 38: self.s.bal[pid] -= self.cfg.luxuryValue; self.s.freeparkingsum += self.cfg.luxuryValue; self._add_event("tax", pid=pid, kind="luxury", amount=self.cfg.luxuryValue); return

    def _community_chest(self, pid):
        card = self.s.ccorder[self.s.ccn]; self._add_event("card", pid=pid, deck="cc", card=card, text=CCNAME[card] if card < len(CCNAME) else str(card))
        if card == 0: self.s.tile[pid] = 0; self._passed_go(pid, landed=True)
        elif card == 1: self.s.bal[pid] += 200
        elif card == 2: self.s.bal[pid] -= 50; self.s.freeparkingsum += 50
        elif card == 3: self.s.bal[pid] += 50
        elif card == 4: self.s.goojf[pid] += 1
        elif card == 5: self.s.tile[pid] = 10; self.s.injail[pid] = True; self.s.turn.was_doubles = False
        elif card == 6:
            gain = 50 * (self.s.numalive - 1); self.s.bal[pid] += gain
            for i in range(self.s.num):
                if self.s.isalive[i] and i != pid: self.s.bal[i] -= 50; self._add_event("transfer", from_pid=i, to_pid=pid, amount=50)
        elif card in (7,10,16): self.s.bal[pid] += 100
        elif card == 8: self.s.bal[pid] += 20
        elif card in (9,15): self.s.bal[pid] += 10
        elif card == 11: self.s.bal[pid] -= 100; self.s.freeparkingsum += 100
        elif card == 12: self.s.bal[pid] -= 150; self.s.freeparkingsum += 150
        elif card == 13: self.s.bal[pid] += 25
        elif card == 14:
            pay = sum(115 if self.s.numhouse[i]==5 else 40*self.s.numhouse[i] for i in range(40) if self.s.ownedby[i]==pid and self.s.numhouse[i] not in (0,-1))
            self.s.bal[pid] -= pay; self._add_event("repairs", pid=pid, amount=pay, deck="cc")
        self._add_event("balance", pid=pid, balance=self.s.bal[pid])
        self.s.ccn += 1
        if self.s.ccn > 16: self.rng.shuffle(self.s.ccorder); self.s.ccn = 0

    def _chance(self, pid, distance):
        card = self.s.chanceorder[self.s.chancen]; self._add_event("card", pid=pid, deck="chance", card=card, text=CHANCENAME[card] if card < len(CHANCENAME) else str(card))
        if card == 0: self.s.tile[pid] = 0; self._passed_go(pid, landed=True)
        elif card == 1:
            if self.s.tile[pid] > 24: self._passed_go(pid, landed=False)
            self.s.tile[pid] = 24; self.land(pid, 0)
        elif card == 2:
            if self.s.tile[pid] > 11: self._passed_go(pid, landed=False)
            self.s.tile[pid] = 11; self.land(pid, 0)
        elif card == 3:
            if self.s.tile[pid] <= 12: self.s.tile[pid] = 12
            elif self.s.tile[pid] <= 28: self.s.tile[pid] = 28
            else: self._passed_go(pid, landed=False); self.s.tile[pid] = 12
            t = self.s.tile[pid]; owner = self.s.ownedby[t]
            if owner != pid and owner >= 0 and self.s.ismortgaged[t] != 1:
                amt = distance * 10; self.s.bal[pid] -= amt; self.s.bal[owner] += amt
            else: self.land(pid, 0)
        elif card == 4:
            t = self.s.tile[pid]
            if t <= 5: self.s.tile[pid] = 5
            elif t <= 15: self.s.tile[pid] = 15
            elif t <= 25: self.s.tile[pid] = 25
            elif t <= 35: self.s.tile[pid] = 35
            else: self._passed_go(pid, landed=False); self.s.tile[pid] = 5
            rr = self.s.tile[pid]; owner = self.s.ownedby[rr]
            if owner != pid and owner >= 0 and self.s.ismortgaged[rr] != 1:
                rr_count = sum(1 for p in (5,15,25,35) if self.s.ownedby[p] == owner)
                amt = RRPRICE[rr_count] * 2; self.s.bal[pid] -= amt; self.s.bal[owner] += amt
            else: self.land(pid, 0)
        elif card == 5: self.s.bal[pid] += 50
        elif card == 6: self.s.goojf[pid] += 1
        elif card == 7:
            self.s.tile[pid] -= 3
            if self.s.tile[pid] < 0: self.s.tile[pid] += 40
            self.land(pid, 0)
        elif card == 8: self.s.tile[pid] = 10; self.s.injail[pid] = True; self.s.turn.was_doubles = False
        elif card == 9:
            pay = sum(100 if self.s.numhouse[i]==5 else 25*self.s.numhouse[i] for i in range(40) if self.s.ownedby[i]==pid and self.s.numhouse[i] not in (0,-1))
            self.s.bal[pid] -= pay; self._add_event("repairs", pid=pid, amount=pay, deck="chance")
        elif card == 10: self.s.bal[pid] -= 15; self.s.freeparkingsum += 15
        elif card == 11:
            if self.s.tile[pid] > 5: self._passed_go(pid, landed=False)
            self.s.tile[pid] = 5; self.land(pid, 0)
        elif card == 12: self.s.tile[pid] = 39; self.land(pid, 0)
        elif card == 13:
            pay = 50 * (self.s.numalive - 1); self.s.bal[pid] -= pay
            for i in range(self.s.num):
                if self.s.isalive[i] and i != pid: self.s.bal[i] += 50
        elif card == 14: self.s.bal[pid] += 150
        elif card == 15: self.s.bal[pid] += 100
        self._add_event("balance", pid=pid, balance=self.s.bal[pid])
        self.s.chancen += 1
        if self.s.chancen > 15: self.rng.shuffle(self.s.chanceorder); self.s.chancen = 0

    def _pay_rr_util(self, pid, owner, tile, distance):
        if tile in (12,28):
            both = self.s.ownedby[12] == self.s.ownedby[28]; mult = 10 if both else 4; amt = distance * mult
            self.s.bal[pid] -= amt; self.s.bal[owner] += amt; self._add_event("rent", kind="utility", pid=pid, owner=owner, tile=tile, amount=amt); return
        if tile in (5,15,25,35):
            rr_count = sum(1 for p in (5,15,25,35) if self.s.ownedby[p] == owner); amt = RRPRICE[rr_count]
            self.s.bal[pid] -= amt; self.s.bal[owner] += amt; self._add_event("rent", kind="rr", pid=pid, owner=owner, tile=tile, amount=amt)

    def _pay_property_rent(self, pid, owner, tile):
        is_monopoly = any(tile in group and all(self.s.ownedby[p] == owner for p in group) for group in PROPGROUPS.values())
        if is_monopoly and self.s.numhouse[tile] == 0: rent = 2 * RENTPRICE[tile*6]
        else: rent = RENTPRICE[(tile*6) + self.s.numhouse[tile]]
        self.s.bal[pid] -= rent; self.s.bal[owner] += rent; self._add_event("rent", kind="property", pid=pid, owner=owner, tile=tile, amount=rent)

    def forfeit_current_player(self):
        pid = self.cur()
        for i in range(40):
            if self.s.ownedby[i] == pid: self.s.ownedby[i] = -1; self.s.numhouse[i] = max(0, self.s.numhouse[i]) if self.s.numhouse[i] > 0 else self.s.numhouse[i]; self.s.ismortgaged[i] = 0 if self.s.ismortgaged[i] > 0 else self.s.ismortgaged[i]
        self.s.numalive -= 1; self.s.isalive[pid] = False; self.s.injail[pid] = False
        self._add_event("forfeit", pid=pid, remaining_alive=self.s.numalive)

    def end_turn(self):
        pid = self.cur(); self._add_event("turn_end", pid=pid, balance=self.s.bal[pid]); self.s.turn.rolled = None; self.advance_to_next_player()

    def mortgage_tile(self, tile):
        pid = self.cur()
        if self.s.ownedby[tile] != pid: raise RuntimeError("not owner")
        if self.s.ismortgaged[tile] != 0: raise RuntimeError("already mortgaged")
        self.s.ismortgaged[tile] = 1; self.s.bal[pid] += MORTGAGEPRICE[tile]
        self._add_event("mortgage", pid=pid, tile=tile, amount=MORTGAGEPRICE[tile], balance=self.s.bal[pid])

    def unmortgage_tile(self, tile):
        pid = self.cur()
        if self.s.ownedby[tile] != pid: raise RuntimeError("not owner")
        if self.s.ismortgaged[tile] != 1: raise RuntimeError("not mortgaged")
        cost = TENMORTGAGEPRICE[tile]
        if self.s.bal[pid] < cost: raise RuntimeError("cannot afford")
        self.s.ismortgaged[tile] = 0; self.s.bal[pid] -= cost
        self._add_event("unmortgage", pid=pid, tile=tile, cost=cost, balance=self.s.bal[pid])


class MonopolyAI:
    def __init__(self, me, name=None): self.me = me; self.display_name = name or "[AI]"; self.cache = []

    def _get_min_safe(self, s, cfg):
        high = max(cfg.incomeValue, cfg.luxuryValue)
        store = {}
        for p in (5,15,25,35):
            if s.ownedby[p] not in (-1, self.me): store[s.ownedby[p]] = store.get(s.ownedby[p], 0) + 1
        if store: high = max(high, RRPRICE[max(store.values())])
        for group in PROPGROUPS.values():
            monopoly = all(s.ownedby[p] == s.ownedby[group[0]] for p in group) and s.ownedby[group[0]] not in (-1, self.me)
            for prop in group:
                if s.ownedby[prop] in (-1, self.me): continue
                if s.numhouse[prop] == 0 and monopoly: high = max(high, 2 * RENTPRICE[prop * 6])
                else: high = max(high, RENTPRICE[prop * 6 + s.numhouse[prop]])
        if high >= 2000: return 1000
        return int(high - (0.00025 * (high ** 2)))

    def choose_action(self, s, cfg, choices):
        if "roll" in choices: return "roll"
        if s.bal[self.me] < 0:
            for t in range(40):
                if s.ownedby[t] == self.me and s.ismortgaged[t] == 0:
                    self.cache = [t, "d"]; return "mortgage_ai"
        if "end" in choices: return "end"
        if "forfeit" in choices: return "forfeit"
        return choices[0]

    def choose_buy(self, s, cfg, prop_id):
        safe = self._get_min_safe(s, cfg)
        return (s.bal[self.me] - PRICEBUY[prop_id]) >= safe

    def grab_from_cache(self):
        if not self.cache: return "d"
        return self.cache.pop(0)


class MonopolyDirector:
    def __init__(self, engine, ai_map): self.e = engine; self.ai_map = ai_map

    def attach_default_ai(self):
        for i, slot in enumerate(self.e.s.uid):
            if slot.is_ai and i not in self.ai_map: self.ai_map[i] = MonopolyAI(me=i, name=slot.ai_name)

    def step_auto_until_choice(self):
        self.e.clear_events(); self.attach_default_ai()
        while not self.e.game_over():
            pid = self.e.cur()
            if not self.e.s.isalive[pid]: self.e.advance_to_next_player(); continue
            if not self.e.s.uid[pid].is_ai: break
            ai = self.ai_map.get(pid)
            if not ai: break
            acts = self.e.legal_actions(); choice = ai.choose_action(self.e.s, self.e.cfg, acts)
            if choice == "roll":
                if self.e.s.injail[pid]:
                    self.e.jail_roll()
                    if any(ev.kind == "jail_forced_bail" for ev in self.e.events): self.e.pay_bail_and_roll()
                else: self.e.normal_roll()
                t = self.e.s.tile[pid]
                if self.e.s.ownedby[t] == -1:
                    if ai.choose_buy(self.e.s, self.e.cfg, t): self.e.buy_current_tile()
                    else: self.e.decline_buy_current_tile()
                continue
            if choice == "end": self.e.end_turn(); continue
            if choice == "mortgage_ai":
                while True:
                    x = ai.grab_from_cache()
                    if x == "d": break
                    tile = int(x)
                    try:
                        if self.e.s.ismortgaged[tile] == 1: self.e.unmortgage_tile(tile)
                        else: self.e.mortgage_tile(tile)
                    except Exception: pass
                continue
            if choice == "forfeit": self.e.forfeit_current_player(); self.e.end_turn(); continue
            break
        if self.e.game_over():
            w = self.e.winner()
            if w is not None: self.e._add_event("game_over", winner=w)
        return self.e.events


def _state_text(s: MonopolyState) -> str:
    lines = []
    for i, slot in enumerate(s.uid):
        if not s.isalive[i]: continue
        name = slot.ai_name if slot.is_ai else f"<@{slot.user_id}>"
        jail = " :red_square:" if s.injail[i] else ""
        cur = " *(your turn)*" if i == s.p else ""
        lines.append(f"{name}: `${s.bal[i]}` | {TILENAME[s.tile[i]]}{jail}{cur}")
    return "\n".join(lines) or "no players"

def _events_text(events: List[EngineEvent]) -> str:
    out = []
    for e in events:
        k = e.kind; d = e.data
        if k == "rolled": out.append(f":game_die: Rolled `{d['d1']}` + `{d['d2']}` = `{d['d1']+d['d2']}`")
        elif k == "moved": out.append(f":arrow_right: Moved to `{TILENAME[d['to_tile']]}`")
        elif k == "rent": out.append(f":moneybag: Paid `${d['amount']}` rent on `{TILENAME[d.get('tile',0)]}`")
        elif k == "bought": out.append(f":house: Bought `{TILENAME[d['tile']]}` for `${d['price']}`")
        elif k == "go_to_jail": out.append(":rotating_light: Sent to jail!")
        elif k == "bail_paid": out.append(f":key: Paid bail `${d['bail']}`")
        elif k == "free_parking": out.append(f":tada: Free Parking! +`${d['amount']}`")
        elif k == "card": out.append(f":cards: {d.get('deck','').upper()}: _{d.get('text','?')}_")
        elif k == "buy_offer": out.append(f":label: Land on `{TILENAME[d['tile']]}` — cost `${d['price']}` (buy or decline)")
        elif k == "go_money": out.append(f":regional_indicator_g: Passed GO! +`${d['amount']}`")
        elif k == "tax": out.append(f":receipt: {d['kind'].title()} Tax: -`${d['amount']}`")
        elif k == "game_over": out.append(":trophy: Game Over!")
        elif k == "forfeit": out.append(f":white_flag: Player {d['pid']+1} forfeited")
    return "\n".join(out[-8:])

def _property_card(tile: int) -> str:
    if tile < 0 or tile >= 40 or PRICEBUY[tile] <= 0: return ""
    lines = [f"*{TILENAME[tile]}*", f"Price: `${PRICEBUY[tile]}`"]
    if PROPCOLORS[tile] == "rr":
        lines.append("Railroad"); lines += [f"{i} RR owned: `${p}`" for i, p in enumerate(RRPRICE[1:], start=1)]
        return "\n".join(lines)
    if PROPCOLORS[tile] == "utility":
        lines += ["Utility", "1 utility: 4× dice", "2 utilities: 10× dice"]; return "\n".join(lines)
    base = RENTPRICE[tile*6]; lines.append(f"Rent: `${base}`")
    for i in range(1,5): lines.append(f"{i} houses: `${RENTPRICE[tile*6+i]}`")
    lines += [f"Hotel: `${RENTPRICE[tile*6+5]}`", f"House cost: `${HOUSEPRICE[tile]}`", f"Mortgage: `${MORTGAGEPRICE[tile]}`"]
    return "\n".join(lines)

def _render_blocks(engine: MonopolyEngine, events: List[EngineEvent], channel_id: str, uid: str) -> list:
    s = engine.s; pid = s.p; acts = engine.legal_actions(); slot = s.uid[pid]
    current_name = slot.ai_name if slot.is_ai else f"<@{slot.user_id}>"
    state_str = _state_text(s); ev_str = _events_text(events)
    tile = s.tile[pid]; card = _property_card(tile)
    text = f":game_die: *Monopoly* | Turn: {current_name}\n\n*Players:*\n{state_str}"
    if card: text += f"\n\n*On {TILENAME[tile]}:*\n{card}"
    if ev_str: text += f"\n\n*Log:*\n{ev_str}"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text[:2900]}}]
    btns = []
    if "roll" in acts:
        btns.append({"type": "button", "text": {"type": "plain_text", "text": ":game_die: Roll"}, "action_id": "mono_roll", "style": "primary", "value": f"{channel_id}:{uid}"})
    if "bail" in acts:
        btns.append({"type": "button", "text": {"type": "plain_text", "text": "Pay Bail"}, "action_id": "mono_bail", "value": f"{channel_id}:{uid}"})
    if "use_goojf" in acts:
        btns.append({"type": "button", "text": {"type": "plain_text", "text": "Use GOOJF"}, "action_id": "mono_goojf", "value": f"{channel_id}:{uid}"})
    if s.ownedby[tile] == -1 and s.turn.rolled is not None and not slot.is_ai:
        price = PRICEBUY[tile]; can_afford = s.bal[pid] >= price
        btns.append({"type": "button", "text": {"type": "plain_text", "text": f"Buy (${price})"}, "action_id": "mono_buy", "value": f"{channel_id}:{uid}", **({"style": "primary"} if can_afford else {})})
        btns.append({"type": "button", "text": {"type": "plain_text", "text": "Decline"}, "action_id": "mono_decline", "value": f"{channel_id}:{uid}"})
    if "end" in acts:
        btns.append({"type": "button", "text": {"type": "plain_text", "text": "End Turn"}, "action_id": "mono_end", "value": f"{channel_id}:{uid}"})
    if "forfeit" in acts:
        btns.append({"type": "button", "text": {"type": "plain_text", "text": ":white_flag: Forfeit"}, "action_id": "mono_forfeit", "style": "danger", "value": f"{channel_id}:{uid}"})
    if btns:
        for chunk in [btns[i:i+5] for i in range(0, len(btns), 5)]:
            blocks.append({"type": "actions", "elements": chunk})
    return blocks


TOKEN_COLORS = [(231,76,60),(52,152,219),(46,204,113),(241,196,15),(155,89,182),(230,126,34),(26,188,156),(149,165,166)]

class MonopolyBoardRenderer:
    def __init__(self, board_path="monopoly-board.png"):
        self.board_path = board_path; self.base = None; self.cache: Dict[str, bytes] = {}

    def _load(self):
        if self.base is None and PIL_AVAILABLE and os.path.exists(self.board_path):
            import hashlib as _h
            self.base = Image.open(self.board_path).convert("RGBA")

    def render(self, state: MonopolyState) -> Optional[bytes]:
        self._load()
        if not self.base or not PIL_AVAILABLE: return None
        import hashlib
        key = hashlib.md5(state.to_json().encode()).hexdigest()
        if key in self.cache: return self.cache[key]
        img = self.base.copy(); draw = ImageDraw.Draw(img); w, h = img.size
        m = int(w * 0.065); s = (w - 2 * m) // 9; positions = [(w - m, h - m)]
        for i in range(1,10): positions.append((w - m - i * s, h - m))
        for i in range(1,10): positions.append((m, h - m - i * s))
        for i in range(1,10): positions.append((m + i * s, m))
        for i in range(1,9): positions.append((w - m, m + i * s))
        token_size = int(w * 0.03); outline = max(2, token_size // 8)
        for i, alive in enumerate(state.isalive):
            if not alive: continue
            if state.tile[i] >= len(positions): continue
            x, y = positions[state.tile[i]]; ox = (i%3)*(token_size+4); oy = (i//3)*(token_size+4)
            cx = int(x+ox-token_size//2); cy = int(y+oy-token_size//2)
            draw.ellipse((cx-outline,cy-outline,cx+token_size+outline,cy+token_size+outline), fill=(255,255,255,255))
            draw.ellipse((cx,cy,cx+token_size,cy+token_size), fill=TOKEN_COLORS[i])
        buf = io.BytesIO(); img.save(buf, format="PNG"); self.cache[key] = buf.getvalue(); return self.cache[key]


_games: dict[str, dict] = {}
DB_PATH = "data/monopoly.db"


def _db(q, p=(), fetch=False, one=False):
    os.makedirs("data", exist_ok=True)
    con = sqlite3.connect(DB_PATH); cur = con.cursor(); cur.execute(q, p); out = None
    if fetch: out = cur.fetchone() if one else cur.fetchall()
    con.commit(); con.close(); return out


def _save(channel_id, engine):
    _db("CREATE TABLE IF NOT EXISTS games (channel_id TEXT PRIMARY KEY, state_json TEXT)")
    _db("INSERT INTO games(channel_id,state_json) VALUES(?,?) ON CONFLICT(channel_id) DO UPDATE SET state_json=excluded.state_json", (channel_id, engine.s.to_json()))

def _load(channel_id):
    try:
        _db("CREATE TABLE IF NOT EXISTS games (channel_id TEXT PRIMARY KEY, state_json TEXT)")
        row = _db("SELECT state_json FROM games WHERE channel_id=?", (channel_id,), fetch=True, one=True)
        return MonopolyState.from_json(row[0]) if row else None
    except Exception: return None

def _delete(channel_id):
    try: _db("DELETE FROM games WHERE channel_id=?", (channel_id,))
    except Exception: pass


_renderer = MonopolyBoardRenderer()


async def _post_game(client, channel, engine, uid, events=None, ts=None):
    events = events or engine.events; blocks = _render_blocks(engine, events, channel, uid)
    if ts:
        try: await client.chat_update(channel=channel, ts=ts, blocks=blocks, text="Monopoly"); return ts
        except Exception: pass
    result = await client.chat_postMessage(channel=channel, blocks=blocks, text="Monopoly")
    return result.get("ts")

async def _advance_ai(client, channel, engine, uid, ts):
    director = MonopolyDirector(engine, {}); director.step_auto_until_choice()
    if engine.game_over():
        w = engine.winner()
        winner_name = (engine.s.uid[w].ai_name if engine.s.uid[w].is_ai else f"<@{engine.s.uid[w].user_id}>") if w is not None else "?"
        blocks = _render_blocks(engine, engine.events, channel, uid)
        await client.chat_update(channel=channel, ts=ts, blocks=[{"type":"section","text":{"type":"mrkdwn","text":f":trophy: *Game over!* {winner_name} wins!"}}], text="Monopoly game over")
        _delete(channel); _games.pop(channel, None); return ts
    _save(channel, engine); return await _post_game(client, channel, engine, uid, ts=ts)

async def _handle_action(ack, body, client, action):
    await ack()
    val = body["actions"][0].get("value",""); parts = val.split(":", 1)
    channel = parts[0]; uid = parts[1] if len(parts)>1 else body["user"]["id"]; actor = body["user"]["id"]
    game = _games.get(channel)
    if not game: return
    engine: MonopolyEngine = game["engine"]; ts = game.get("ts")
    pid = engine.cur(); slot = engine.s.uid[pid]
    if not slot.is_ai and slot.user_id != actor:
        await client.chat_postEphemeral(channel=channel, user=actor, text="not your turn"); return
    engine.clear_events()
    try:
        if action == "roll":
            if engine.s.injail[pid]:
                engine.jail_roll()
                if any(ev.kind == "jail_forced_bail" for ev in engine.events): engine.pay_bail_and_roll()
            else: engine.normal_roll()
            t = engine.s.tile[pid]
            if engine.s.ownedby[t] == -1 and slot.is_ai: engine.buy_current_tile()
        elif action == "buy": engine.buy_current_tile()
        elif action == "decline": engine.decline_buy_current_tile()
        elif action == "bail": engine.pay_bail_and_roll()
        elif action == "goojf": engine.use_goojf_and_roll()
        elif action == "end": engine.end_turn()
        elif action == "forfeit": engine.forfeit_current_player(); engine.end_turn()
    except Exception as e:
        await client.chat_postEphemeral(channel=channel, user=actor, text=f"error: {e}"); return
    if engine.game_over():
        w = engine.winner()
        winner_name = (engine.s.uid[w].ai_name if engine.s.uid[w].is_ai else f"<@{engine.s.uid[w].user_id}>") if w is not None else "?"
        if ts: await client.chat_update(channel=channel, ts=ts, blocks=[{"type":"section","text":{"type":"mrkdwn","text":f":trophy: *Game over!* {winner_name} wins!"}}], text="Monopoly game over")
        _delete(channel); _games.pop(channel, None); return
    _save(channel, engine); new_ts = await _post_game(client, channel, engine, uid, ts=ts)
    game["ts"] = new_ts
    if engine.s.uid[engine.cur()].is_ai:
        game["ts"] = await _advance_ai(client, channel, engine, uid, new_ts)


async def setup(app):
    _db("CREATE TABLE IF NOT EXISTS games (channel_id TEXT PRIMARY KEY, state_json TEXT)")

    @app.command("/monopoly_start")
    async def monopoly_start(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        import re as re_mod
        if channel in _games:
            await client.chat_postEphemeral(channel=channel, user=uid, text="a game is already running here — use /monopoly_stop first"); return
        text = (command.get("text") or "").strip()
        m = re_mod.search(r"<@([A-Z0-9]+)>", text)
        players = [PlayerSlot(uid)]
        if m:
            opponent_id = m.group(1)
            if opponent_id == uid:
                await client.chat_postEphemeral(channel=channel, user=uid, text="can't play against yourself"); return
            players.append(PlayerSlot(opponent_id))
        else:
            players.append(PlayerSlot("ai", is_ai=True, ai_name="[AI]"))
        engine = MonopolyEngine.new_game(players, GameConfig())
        game = {"engine": engine, "ts": None}; _games[channel] = game; _save(channel, engine)
        director = MonopolyDirector(engine, {}); director.step_auto_until_choice()
        ts = await _post_game(client, channel, engine, uid)
        game["ts"] = ts
        if engine.s.uid[engine.cur()].is_ai:
            game["ts"] = await _advance_ai(client, channel, engine, uid, ts)

    @app.command("/monopoly_stop")
    async def monopoly_stop(ack, command, client):
        await ack()
        channel = command["channel_id"]; uid = command["user_id"]
        _delete(channel); _games.pop(channel, None)
        await client.chat_postMessage(channel=channel, text="monopoly game stopped")

    @app.command("/monopoly_resume")
    async def monopoly_resume(ack, command, client):
        await ack()
        channel = command["channel_id"]; uid = command["user_id"]
        if channel in _games:
            await client.chat_postEphemeral(channel=channel, user=uid, text="a game is already active here"); return
        state = _load(channel)
        if not state:
            await client.chat_postEphemeral(channel=channel, user=uid, text="no saved monopoly game in this channel"); return
        engine = MonopolyEngine(state, GameConfig()); game = {"engine": engine, "ts": None}; _games[channel] = game
        ts = await _post_game(client, channel, engine, uid)
        game["ts"] = ts
        if engine.s.uid[engine.cur()].is_ai:
            game["ts"] = await _advance_ai(client, channel, engine, uid, ts)

    @app.action("mono_roll")
    async def mono_roll(ack, body, client): await _handle_action(ack, body, client, "roll")
    @app.action("mono_buy")
    async def mono_buy(ack, body, client): await _handle_action(ack, body, client, "buy")
    @app.action("mono_decline")
    async def mono_decline(ack, body, client): await _handle_action(ack, body, client, "decline")
    @app.action("mono_bail")
    async def mono_bail(ack, body, client): await _handle_action(ack, body, client, "bail")
    @app.action("mono_goojf")
    async def mono_goojf(ack, body, client): await _handle_action(ack, body, client, "goojf")
    @app.action("mono_end")
    async def mono_end(ack, body, client): await _handle_action(ack, body, client, "end")
    @app.action("mono_forfeit")
    async def mono_forfeit(ack, body, client): await _handle_action(ack, body, client, "forfeit")
