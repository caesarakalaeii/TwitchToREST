class Broadcaster:
    
    twitch_login: str
    twitch_id: str
    steam_id: int
    redeem_ids: dict
    referral: str
    
    def __init__(self,twitch_id:str, twitch_login:str, steam_id:int, redeem_ids:dict, referral:str) -> None:
        self.twitch_id = twitch_id
        self.twitch_login = twitch_login
        self.steam_id = steam_id
        self.redeem_ids = redeem_ids
        self.referral = referral
        pass
    
    def to_dict(self, redeem = True):
        base = {
            'Referral': self.referral,
            'TwitchId': self.twitch_id,
            'TwitchLogin': self.twitch_login,
            'SteamId': self.steam_id
        }
        if redeem:
            base.update({'RedeemIds': self.redeem_ids})
        return base
    
