class Broadcaster:
    
    username: str
    id: str
    steam_id: int
    redeem_ids: dict
    referral: str
    
    def __init__(self,id:str, username:str, steam_id:int, redeem_ids:dict, referral:str) -> None:
        self.id = id
        self.username = username
        self.steam_id = steam_id
        self.redeem_ids = redeem_ids
        self.referral = referral
        pass
    
    def to_dict(self):
        return {
            'Referral': self.referral,
            'Id': self.id,
            'Username': self.username,
            'SteamId': self.steam_id,
            'RedeemIds': self.redeem_ids
        }
    
