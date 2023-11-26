
# TODO: Redo all of this, not working and/or stupid

class Event:
    '''
    Class representing a twitchbased Event to easily convert the needed data into json
    '''
    event_type: str
    steam_id:str
    username: str
    broadcaster: str
    message: str = None
    
    def __init__(self, broadcaster:str, username:str, steam_id:str, message:str = None):
        self.broadcaster = broadcaster
        self.username = username
        self.message = message
        self.steam_id = steam_id
    
    def to_json_dict(self):
        '''
        Returns a dict to use in quarts jsonify filled with the event's data and type
        '''
        base = {
            'EventType': self.event_type,
            'Username': self.username,
            'Broadcaster': self.broadcaster,
            'SteamId': self.steam_id
        }
        if not (self.message == None or self.message == ""):
            base.update({'Message': self.message})
        
        return base
    
class Follow(Event):
    '''
    Class representing a twitchbased follow Event to easily convert the needed data into json
    '''
    
    def __init__(self, broadcaster: str, username: str, steam_id:str, message: str = None):
        self.event_type = 'Follow'
        super().__init__(broadcaster, username,steam_id, message)
    
    def to_json_dict(self):
        return super().to_json_dict()
    

class Sub(Event):
    '''
    Class representing a twitchbased subscribtion Event to easily convert the needed data into json
    '''
    tier: int
    total_time: int
    streak: int
    
    def __init__(self, broadcaster: str, username: str, steam_id:str, tier:int, total_time:int, streak:int, message: str = None):
        super().__init__(broadcaster, username, steam_id, message)
        self.event_type = 'Sub'
        self.tier: int = tier
        self.total_time: int = total_time
        self.streak: int = streak
    
    def to_json_dict(self):
        base = super().to_json_dict()
        base.update({
            'Tier': self.tier,
            'TotalTime': self.total_time,
            'Streak': self.streak
        })
        return base
    
    
    
class SubBomb(Event):
    '''
    Class representing a twitchbased multi subscribtion (subbomb) Event to easily convert the needed data into json
    '''
    event_type:str
    amount: int
    tier: int
    
    def __init__(self, broadcaster: str, username: str, steam_id:str, tier: int, amount, message: str = None):
        super().__init__(broadcaster, username, steam_id, message)
        self.event_type = 'SubBomb'
        self.amount = amount
        self.tier = tier
    
    def to_json_dict(self):
        base = super().to_json_dict()
        base.update({
            'Tier': self.tier,
            'Amount': self.amount
        })
        return base

class Gift(Event):
    '''
    Class representing a twitchbased gift event to easily convert the needed data into json
    '''
    
    
    gifter_name: str
    tier: int
    
    def __init__(self, broadcaster: str, username: str, steam_id:str, gifter_name:str, tier:int, message: str = None):
        super().__init__(broadcaster, username, steam_id, message)
        self.event_type = 'Gift'
        self.gifter_name = gifter_name
        self.tier = tier
    
    def to_json_dict(self):
        base = super().to_json_dict()
        base.update({
            'Tier': self.tier,
            'GifterName': self.gifter_name
        })
        return 
    
class Redeem(Event):
    '''
    Class representing a twitchbased redeem event to easily convert the needed data into json
    '''
    
    event_type: str
    redeem_type: str
    
    def __init__(self, broadcaster: str, username: str, steam_id:str, redeem_type: str | None, message: str = None):
        super().__init__(broadcaster, username, steam_id, message)
        self.event_type = 'Redeem'
        if redeem_type == None:
            raise ValueError("Redeem unkown")
        self.redeem_type = redeem_type
    
    def to_json_dict(self):
        
        base = super().to_json_dict()
        base.update({
            'RedeemType': self.redeem_type
        })
        return base
    
class Bits(Event):
    '''
    Class representing a twitchbased bit event to easily convert the needed data into json
    '''
    
    
    event_type: str
    amount: int
    
    def __init__(self, broadcaster: str, username: str, steam_id:str, amount:int, message: str = None):
        super().__init__(broadcaster, username, steam_id, message)
        self.event_type = 'Bits'
        self.amount = amount
    
    
    def to_json_dict(self):
        return {
            'Amount': self.amount
        }
    
class Raid(Event):
    '''
    Class representing a twitchbased raid event to easily convert the needed data into json
    '''
    
    event_type:str
    amount: int
    
    def __init__(self, broadcaster: str, username: str, steam_id:str, amount:int, message: str = None):
        super().__init__(broadcaster, username, steam_id, message)
        self.event_type = 'Raid'
        self.amount = amount
    
    def to_json_dict(self):
        return {
            'Amount': self.amount

        }