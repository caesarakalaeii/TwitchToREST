

import asyncio
import datetime
import json

import requests
from broadcaster import Broadcaster
from main import Bot


class Vote:
    broadcaster: Broadcaster
    bot:Bot
    voted: list
    
    def __init__(self, broadcaster: Broadcaster, bot:Bot) -> None:
        self.broadcaster = broadcaster
        self.bot = bot
        self.isRunning = False
        self.choice = []
        self.vote_on_going = False
        
        
        
        pass
    
    def reset_choices(self):
        self.choice[0] = 0
        self.choice[1] = 0
        self.choice[2] = 0
        self.choice[3] = 0
    
    async def vote(self):
        while(self.isRunning):
            vote_start = datetime.datetime.now()
            while(self.vote_on_going):
                asyncio.sleep(2)
                await self.update_vote((datetime.datetime.now() - vote_start).total_seconds())
                if(datetime.datetime.now() - vote_start == datetime.timedelta(seconds=30)):  # time to vote
                    self.end_vote()
            asyncio.sleep(120) # time till next vote
        
        
    async def update_vote(self, time:int):
        
        data = {
            "EventType": "VoteOnGoing",
            "SteamId": self.broadcaster.steam_id,
            "Choices": self.choice,
            "Time": time
        }
        await self.POST(data)
    
    async def end_vote(self):
        data = {
            "EventType": "VoteEnd",
            "SteamId": self.broadcaster.steam_id,
            "Choices": self.choice
        }
        await self.POST(data)
        self.reset_choices()
        
        
    async def POST(self, data):
        # Convert the data to JSON format
        json_data = json.dumps(data)

        self.bot.l.info(f'Data ready to send: {json_data}')
        

        # Make the POST request
        response = requests.post(self.bot.endpoint, json=json_data)

        # Check if the request was successful (status code 2xx)
        if response.ok:
            return f'Sucessfully updated Vote for {self.broadcaster.twitch_login}({self.broadcaster.steam_id})'
        else:
            # If the request was unsuccessful, raise an exception with the error message
            response.raise_for_status()
            return f'Error updating Vote for {self.broadcaster.twitch_login}({self.broadcaster.steam_id})'
        
    
    async def register_vote(self, choice:int):
        self.choice[choice] += 1