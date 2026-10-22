import re
KW_SKIP={
        "Plastic Model Kit", "Mushoku Tensei Jobless Reincarnation", "Devastation Studio", "Prime Generations", "Generations War for Cybertron", "Fig  la mode",
         "Transformers Generations Selects", "Transformers Generations Power", "United Leader Class", "	Beach Queens", "Cantabile", "Online", "Memory of Heroines",
         "Hunter x Hunter", "Final Fantasy XVI", "Final Fantasy VII", "Final Fantasy IX", "Chase Possible", "DXF The Grandline", "DFX The Grandline", "SHFiguarts",
         "Little Witch Academia", "Avatar The Last Airbender", "The Rising of the Shield Hero", "Rock Iconz", "The Last of Us", "Rainbow Six Siege", "Shoulder Rider",
         "The Transformers: The Movie Studio Series", "Re Zero Starting Life in Another World", "Starting Life in Another World", "Mystery Minis", "Cinderella Girls",
         "Teenage Mutant Ninja Turtles Ninja", "Magical Creatures", "Star Trek Generations", "Legacy", "Dragon Ball Z", "Gears of War Reloaded", "Relax Time",
         "Grand Order", "Stay Puft", "Jason and the Argonauts", "Print Portrait", "Ganbare Douki chan", "Bobble Head", "NIJISANJI EN", "Sunshine in the Mirror",
         "Real Elite Masterline", "The Transformers The Movie Studio Series", "Aoni Production", "Rise of the Beasts", "Goddess of Victory Nikke", "Star Wars Legendary",
         "Generation One", "Godzilla vs. Kong", "Godzilla x Kong", "Shiny Colors", "Kimetsu No Yaiba", "The Mandalorian & Grogu", "One Punch Man", "Yumemirize", "Swacchao",
         "Star Wars: Maul - Shadow Lord", "Star Wars: Ahsoka", "Jurassic World", "Fine", "Bust",  "L Size", "M Size", "S Size", "II", "Foam", "GigantiX", "Kyunties", "To Love-Ru Darkness"
         "Nendoroid", "Cafe", "LycoReco", "PVC", "Premium", "Masterline", "ED", "Ver", "Figure", "Action", "Complete", "Edition", "Skyrim", "StarCraft", "Sofvimates",
         "Bunny", "Statue", "Plush", "Vinyl", "Revenge of the Sith", "Movie", "Prop", "Taito Kuji", "Taito", "Mario Kart", "Huggy Good Smile", "Justice League", "Monitor Top", "Moderoid",
         "Village", "Fantastic Beasts", "The Horus Heresy", "Series", "Soft", "Real", "Scale", "Original", "Character", "FNex", "Nex", "Pop", "Up", "Parade", "Figure", "Illustration", "Deluxe", "Normal", "Rebels", "Model Replica",
         "Uodenim", "Chihiro", "Magician", "Elf", "Villager", "Antenna", "Shop", "Limited", "Exclusive", "Bonus", "Item", "Scale", "Dunny", "Art", "Collectible", "Menu", "Item", "Design", "Designer", "Anniversary",
         "Set", "Replica", "Life-Size", "Tenitol", "Concept", "Silicone", "Shippuden", "Light Armor", "Version", "A", "Cyber Pets", "Antenna Shop Limited Edition",
         "Regular", "Illustrated", "Kimetsu", "Yaiba", "Noodle Stopper", "Avengers", "Doomsday", "BDS", "Rivals", "Gamerverse", "Format", "Ultra II The Final Challengers",
         "TOHO Daikaiju Favorite Sculptors Line", "TOHO", "POP", "Cyberpunk Edgerunners", "Five Nights", "FNAF", "Six Collection Chibi", "Figures", "ReAction", "III", "Model Kit", "Episode",
         "Doll", "Chinese-Style", "The Shiny Colors", "Masterpiece", "Movie", "Mini", "My Little Pony", "Bishoujo", "BLOOM", "Brickroid", "Figma", "Crane Kick", "The Fandom", "Fandom", "Gwaihir",
         "Classified Nemesis Immortal", "Karasuno", "Surprise", "Brotherhood", "Clothed", "Frieren Beyond Journeys", "Star Wars", "The Clone Wars", "Arc Trooper", "The Mandalorian", "The Phantom Menace",
         "STAP", "The Bad Batch", "Plastic Model", "The New Empire", "Exquisite", "Basic", "Predator: Badlands", "Monitor Buddiez", "Reality Resort", "Rubber", "Grogu",
         "Granite Waves", "Finding Frankie", "Content Warning", "Godzilla x Kong", "LoveLive Hasunosora Girls High School Idol Club", "UDF", "Prestige Line", "Oshi Works", "Figuarts", "Outfit",
         "FiguartsZERO", "IKIGAI", "Interactive Toy", "Tubbz", "Wall Mount", "Roleplay", "Keyring", "SquarePants", "Desktop", "Collection", "Chibi", "Swimsuit",
         "Helmet", "Part", "Diorama", "Evolution Epic", "Display", "Interactive", "Preorder", "Size", "Gorg", "Accessory", "FigZero", "Moderoid", "Wise", "Playset",
         "Kadokawa", "Merchant", "Meets", "Collectoys", "StarCraft", "Autobot", "Battle", "Studio Terrorcon", "Studio", "Smash Changers", "The Last Knight", "War for Cybertron",
         "MDLX", "Lane", "Ichibansho", "GT", "Legends", "Artcanvas", "Daima", "Evangelion", "Cutie1", "Wano", "Refresh", "ZERO", "HLB", "Baseball", "AAA", "Anime"
}
sorted_skips=sorted(KW_SKIP, key=len, reverse=True)
escaped_skips=[re.escape(skip) for skip in sorted_skips]
MASTER_SKIP_PATTERN = re.compile(rf"\b(?:{'|'.join(escaped_skips)})\b", re.IGNORECASE)
