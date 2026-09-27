import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import re
import time
import csv
from typing import Any
from decimal import Decimal, InvalidOperation

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from pydantic import ValidationError
from requests import RequestException

from app.schemas.schemas import ScrapedOffer
from app.models import StatusEnum, StoreEnum, db, Character, Series, Offer, Figure



KNOWN_CHARACTERS_LIST: list[str]=[]
KNOWN_CHARACTERS_DICT: dict[str, set[str]] = {}
KW_BLACKLIST = {"model kit accessory", "throne", "duvet", "bowl", "adventure island", "shower curtain", "card", "lotr replica", "snk robot metal",
                "banknote", "coin", "map", "mask", "surprise piapro characters", "poster", "harry potter role play", "notebook", "foam sword",
                "medalion", "morpher", "ingot", "blanket", "megami device m.s.g.", "ceramic mug", "doom the dark ages replica",
                "bath duck", "purse", "holotape", "keycard", "outfit set", "medallion", "-pack", "doom 2 replica", "nendoroid more", "support item",
                "desk mat", "figure egg", "movie ticket", "upgrade ticket", "parts for nendoroid", "dungeons & dragons foam",
                "cd-rom", "board game", "towel", "aquabeads", "flying bulls", "click system", "harry potter replica", "accessory set"}
URL_BLACKLIST ={
                # random bs
                "https://yatta.pl/Preorder_Lord_of_the_Rings_LARP_Stunt_Prop_Replica_1_1_Sting,321973,p",
                "https://yatta.pl/Lord_of_the_Rings_Replica_1_1_Key_to_Bag_End_15_cm,297840,p",
                "https://yatta.pl/Zack_Snyder_s_Justice_League_Museum_Masterline_Diorama_Bat_T,216489,p",
                "https://yatta.pl/Preorder_Zack_Snyder_s_Justice_League_Museum_Masterline_Dior,216488,p",
                "https://yatta.pl/Preorder_Star_Trek_Die_Cast_Model_La_Sirena_10_cm,321638,p",
                "https://yatta.pl/House_of_the_Dragon_Replica_1_1_Dark_Sister_Sword_Limited_Ed,264194,p",
                "https://yatta.pl/Dragon_Ball_Super_Board_Game_The_Survival_of_the_Universe_En,262802,p",
                "https://yatta.pl/Preorder_ABC_Jumbo_Glitter_Bath_Duck,319283,p",
                "https://yatta.pl/Fallout_Replica_Grognak_the_Barbarian_Holotape,296819,p",
                "https://yatta.pl/Preorder_Fallout_Replica_Security_Keycard_Vault_111_Limited,310550,p",
                "https://yatta.pl/Preorder_Looney_Tunes_Scaled_Prop_Replica_Acme_Anvil_17_cm,321974,p",
                "https://yatta.pl/Pokemon_SV02_Paldea_Evolved_Build_and_Battle_Stadium,233414,p",
                "https://yatta.pl/Preorder_Transformers_Collectable_Coin_Beast_Wars_30th_Anniv,321599,p",
                "https://yatta.pl/Dark_Souls_III_incense_burner_Fog_Gate_19_cm,303636,p",
                "https://yatta.pl/Preorder_Power_Rangers_Medallion_Megazord_Limited_Edition,321597,p",
                "https://yatta.pl/Preorder_Fallout_Plush_Keychain_Stimpak_13_cm,321478,p",
                "https://yatta.pl/Preorder_Star_Wars_The_Mandalorian_and_Grogu_Revell_Model_Ki,312774,p",
                "https://yatta.pl/Preorder_Star_Wars_The_Mandalorian_and_Grogu_Revell_Model_Ki,312775,p",
                "https://yatta.pl/Original_Character_Parts_for_Nendoroid_Doll_Figures_Outfit_S,265222,p",
                "https://yatta.pl/Original_Character_for_Nendoroid_Doll_Figures_Outfit_Set_Wed,247063,p",
                "https://yatta.pl/Original_Character_Parts_for_Nendoroid_Doll_Figures_Outfit_S,247400,p",
                "https://yatta.pl/Original_Character_for_Nendoroid_Doll_Figures_Outfit_Set_Wed,247063,p",
                "https://yatta.pl/Original_Character_for_Nendoroid_Doll_Figures_Outfit_Set_Cla,246612,p",
                "https://yatta.pl/Original_Character_for_Nendoroid_Doll_Figures_Outfit_Set_Cla,246611,p",
                "https://yatta.pl/Preorder_The_Lord_of_the_Rings_Miniature_Environment_Rivende,321627,p",
                "https://yatta.pl/Preorder_Lord_of_the_Rings_Mini_Statue_Skull_of_a_Misty_Moun,308597,p",
                "https://yatta.pl/Preorder_Doom_The_Dark_Ages_Replica_Secret_Key_Limited_Editi,312659,p",
                "https://yatta.pl/Preorder_Rebuild_of_Evangelion_SYUTO_Tiny_Scale_Plastic_Mode,320012,p",
                "https://yatta.pl/Preorder_Rebuild_of_Evangelion_Moderoid_Plastic_Model_Kit_Ev,320049,p",
                "https://yatta.pl/Preorder_Mr_Beast_Lab_Hybrids_Series_2_Mini_Figuren_2er_Pack,299174,p",
                "https://yatta.pl/Mr_Beast_Lab_Swarms_Series_2_Mini_Figuren_2er_Pack_Atomic_Se,299155,p",
                "https://yatta.pl/Preorder_Megami_Device_M_S_G_Plastic_Model_Kit_1_1_Yggdrasis,321795,p",
                "https://yatta.pl/Nendoroid_Accessories_for_Nendoroid_Doll_Figures_Outfit_Set,280582,p",
                "https://yatta.pl/One_Piece_Light_Up_Figure_Devil_Fruit_8_cm,228445,p",
                "https://yatta.pl/Preorder_Cutie_Honey_Nova_Plamatea_Plastic_Model_Kit_Honey_C,321695,p",
                "https://yatta.pl/The_Transformers_The_Movie_Studio_Series_Roleplay_Replica_Th,321537,p",
                "https://yatta.pl/Preorder_Transformers_Replica_The_Movie_40th_Anniversary_Mov,321598,p",
                "https://yatta.pl/Heroes_of_Goo_Jit_Zu_Meteor_Madness_Stretch_Figure_Thrash_12,283806,p",
                "https://yatta.pl/Preorder_Kotobukiya_M_S_G_Model_Kit_Accessory_Set_Mecha_Supp,305008,p",
                "https://yatta.pl/Resident_Evil_4_Replica_1_1_Metal_Exclusive_Upgrade_Ticket,270753,p",
                "https://yatta.pl/Nendoroid_Doll_Parts_for_Nendoroid_Doll_Figures_Mermaid_Set,266379,p",
                "https://yatta.pl/Star_Wars_Episode_I_Model_Kit_Gift_Set_1_120_Darth_Mauls_Sit,258426,p",
                "https://yatta.pl/Harry_Potter_Hermine_s_Time_Turner,32495,p",
                "https://yatta.pl/Harry_Potter_Sirius_Black_s_Wand,32494,p",
                "https://yatta.pl/Harry_Potter_Sirius_Black_s_Wand,32494,p",
                "https://yatta.pl/Harry_Potter_Collector_Gift_Box_Harry_Potter_s_Journey_to_Ho,216045,p",
                "https://yatta.pl/Harry_Potter_Kids_Wizard_Robe_Slytherin,141435,p",
                "https://yatta.pl/Harry_Potter_Plush_Figure_with_Sound_Sorting_Hat_22_cm_Engli,214213,p",
                "https://yatta.pl/Harry_Potter_Prop_Replica_1_1_Golden_Egg_23_cm,78731,p",
                "https://yatta.pl/Harry_Potter_Replica_1_1_Basilisk_Fang_and_Tom_Riddle_Diary,77835,p",
                "https://yatta.pl/Harry_Potter_Replica_1_1_Deluminator,37803,p",
                "https://yatta.pl/Harry_Potter_Replica_1_1_Firebolt_Broom,42133,p",
                "https://yatta.pl/Harry_Potter_Replica_1_1_Hermione_s_Bag,176020,p",
                "https://yatta.pl/Harry_Potter_Replica_Bellatrix_Lestrange_s_Wand_35_cm,42134,p",
                "https://yatta.pl/Harry_Potter_Replica_Sorcerer_s_Stone,32479,p",
                "https://yatta.pl/Harry_Potter_Replica_The_Hufflepuff_Cup,44557,p",
                "https://yatta.pl/Harry_Potter_Role_Play_Wand_Harry_Potter_30_cm,289758,p",
                "https://yatta.pl/Harry_Potter_Role_Play_Wand_Lord_Voldemort_30_cm,289760,p",
                "https://yatta.pl/Harry_Potter_Role_Play_Wand_The_Elder_Wand_30_cm,289761,p",
                "https://yatta.pl/Harry_Potter_Ten_Character_Wand_Display,32466,p",
                "https://yatta.pl/Harry_Potter_twin_pack_Role_Play_Wands_Harry_Potter_Ginny_We,289756,p",
                "https://yatta.pl/Harry_Potter_twin_pack_Role_Play_Wands_The_Elder_Lord_Voldem,289766,p",
                "https://yatta.pl/Harry_Potter_Wand_Collection_Weasley_Twins,39450,p",
                "https://yatta.pl/Harry_Potter_Wand_Replica_Hermione_38_cm,181315,p",
                "https://yatta.pl/Harry_Potter_Wand_Replica_in_Ollivanders_Box_Luna_Lovegood_3,256873,p",
                "https://yatta.pl/Preorder_Harry_Potter_Celebration_Wand_Harry_Potter_25th_Ann,307317,p",
                "https://yatta.pl/Preorder_Harry_Potter_Tiny_Adventures_Book_Nook_Mini_Diorama,314643,p",
                "https://yatta.pl/Preorder_Nintendo_Mario_Kart_Carrera_First_Race_Track_Set_Ma,314681,p",
                "https://yatta.pl/Preorder_World_of_Nintendo_Super_Mario_Playset_Bowser_Battle,263560,p",
                "https://yatta.pl/Star_Wars_Episode_IV_Replica_1_1_Black_Chrome_Darth_Vader_He,278543,p",
                "https://yatta.pl/Harry_Potter_Hermione_Granger_s_Wand,32498,p",
                "https://yatta.pl/Destiny_Replica_Plaque_Ace_of_Spades_30_cm,289315,p",
                "https://yatta.pl/Preorder_Aquabeads_Craft_Studio_Starter_Set,313955,p",
                "https://yatta.pl/Preorder_Red_Bull_Racing_Click_System_Model_Kit_RB21,314661,p",
                "https://yatta.pl/Preorder_McLaren_Click_System_Kit_MCL39,314662,p",
                "https://yatta.pl/Preorder_McLaren_Click_System_Kit_MCL39,314662,p",
                "https://yatta.pl/Resident_Evil_4_Replica_1_1_Insignia_Key,270756,p",
                "https://yatta.pl/Resident_Evil_4_Replica_1_1_Wayshrine_Key,270757,p",
                "https://yatta.pl/Harry_Potter_Replica_Crystal_Goblet,35783,p",
                "https://yatta.pl/Harry_Potter_Voldemort_s_Wand,32492,p",
                "https://yatta.pl/Harry_Potter_Replica_1_1_The_Horcrux_Locket,40430,p",
                "https://yatta.pl/Preorder_Monster_Jam_Revell_Build_Play_Kit_Monster_Jam_Grave,314660,p",
                "https://yatta.pl/Preorder_Monster_Jam_Revell_Build_Play_Kit_Monster_Jam_Max_D,314659,p",
                "https://yatta.pl/Preorder_Megami_Device_M_S_G_Plastic_Model_Kit_1_1_Desire_Ma,322099,p",
                "https://yatta.pl/Preorder_Heroes_of_Goo_Jit_Zu_Meteor_Madness_Stretch_Figures,283810,p",
                "https://yatta.pl/Preorder_Warhammer_40_000_Captain_MkX_Helmet_Ultramarines_30,308960,p",
                "https://yatta.pl/Attack_on_Titan_Ceramic_Mug_Levi,286675,p",
                "https://yatta.pl/The_Elder_Scrolls_Skyrim_Replica_Dragonborn_Helmet_Limited_E,283007,p",
                "https://yatta.pl/Preorder_One_Piece_Shot_Glass_Set_Barrel_8_cm,322710,p",
                "https://yatta.pl/Preorder_Fallout_Helmet_X_01_10_cm,313579,p",
                "https://yatta.pl/Preorder_Takahiro_Kagami_PVC_Artist_Support_Item_Hand_1_1_Ha,256878,p",
                "https://yatta.pl/Preorder_Borderlands_Replica_Gold_Key,296847,p",
                "https://yatta.pl/Preorder_Lilo_Stitch_Glass_Tumbler_with_Straws_Stitch_485_ml,290777,p",
                "https://yatta.pl/NieR_Automata_Ver1_1a_Notebook,305784,p",
                "https://yatta.pl/The_Hobbit_An_Unexpected_Journey_Statue_13_Apple_Orchard_20,167813,p",
                "https://yatta.pl/Mot_rhead_Shower_Curtain_Warpig_Logo,145956,p",
                "https://yatta.pl/Kit_Rae_Swords_of_the_Ancients_Replica_Savathos_Mithrodin_Wa,318818,p",
                "https://yatta.pl/Preorder_One_Piece_Deluxe_Model_Kit_Collector_Ship_Going_Mer,312618,p",
                "https://yatta.pl/Solar_Spinner_Revolving_Stage_for_Action_Figures,77124,p",
                "https://yatta.pl/Preorder_Fast_Furious_Model_Kit_Brian_s_1999_Nissan_Skyline,314663,p",
                "https://yatta.pl/Preorder_Care_Bears_3D_Sticker_Maker_Refills,317884,p",
                "https://yatta.pl/Preorder_Court_of_the_Dead_Interactive_Light_Up_Sign_and_App,189894,p",
                "https://yatta.pl/Texas_Chainsaw_Massacre_Figure_Chainsaw_with_Sound_76_cm,243470,p",
                "https://yatta.pl/James_Bond_Model_Kit_1_24_Aston_Martin_DB5_21_cm,287917,p",
                "https://yatta.pl/Legend_of_Zelda_Skyward_Sword_Plastic_Replica_Link_s_Hylian,71937,p",
                "https://yatta.pl/Preorder_Bluey_Playset_Food_Truck,312605,p",
                "https://yatta.pl/Preorder_Bluey_Playset_Mini_Heelers_Home,312599,p",
                "https://yatta.pl/Preorder_Bluey_Playset_Tree,312598,p",
                "https://yatta.pl/Preorder_Avatar_The_Last_Airbender_Replica_Aang_s_Glider,308313,p",
                "https://yatta.pl/Preorder_Avatar_The_Last_Airbender_Replica_Waterbending_Scro,308312,p",
                "https://yatta.pl/Preorder_Book_Nook_The_Secret_Rhythm_23_x_11_cm,306985,p",
                "https://yatta.pl/Knight_Rider_Gift_Box_F_L_A_G_Agent_Kit,215617,p",
                "https://yatta.pl/Biker_Mice_From_Mars_Vehicle_Throttle_s_Martian_Monster_Bike,239138,p",
                "https://yatta.pl/Biker_Mice_From_Mars_Action_Figure_Throttle_18_cm,235656,p",
                "https://yatta.pl/Preorder_Bluey_Figure_Pack_Heeler_Family_Road_Trip,312601,p",
                "https://yatta.pl/Wonder_Women_1_1_God_Killer_Elite_Edition_79_cm,227257,p",
                "https://yatta.pl/Transformers_Replica_Matrix_of_Leadership_Metal_Limited_Edit,283010,p",
                "https://yatta.pl/LOTR_Replica_1_1_Sword_of_King_Theoden_Herugrim_92_cm,226418,p",
                "https://yatta.pl/LOTR_Replica_1_1_Aeglos_Spear_of_Gil_galad_259_cm,287891,p",
                "https://yatta.pl/Preorder_Alien_Romulus_Model_Life_Size_Replica_Pulse_Rifle_H,310612,p",
                "https://yatta.pl/Minecraft_Mega_Squishme_Anti_Stress_Figure_Series_2_Tuxedo_1,260772,p",
                "https://yatta.pl/Iron_Maiden_Model_Kit_1_144_Boeing_747_400_Ed_Force_One_49_c,287882,p",
                "https://yatta.pl/Dead_Space_Replica_Isaac_Helmet_Limited_Edition_23_cm,280346,p",
                "https://yatta.pl/Legend_of_Zelda_Plush_Figure_Hylian_Shield_40_cm,162531,p",
                "https://yatta.pl/Preorder_Five_Nights_at_Freddy_s_Replica_Security_Badge_Anti,303810,p",
                "https://yatta.pl/Warhammer_Foam_sword_Armoury_Vanguard_Imperial_Arming_Sword,287394,p",
                "https://yatta.pl/Warhammer_Foam_sword_Armoury_Stalwart_Imperial_Arming_Sword,287395,p",
                "https://yatta.pl/Warhammer_Foam_sword_Armoury_Reikland_Imperial_Arming_Sword,287393,p",
                "https://yatta.pl/Warhammer_Foam_sword_Armoury_Imperial_Flamberge_150_cm,309298,p",
                "https://yatta.pl/Preorder_Warhammer_Foam_war_hammer_Armoury_Ghal_Maraz_125_cm,301287,p",
                "https://yatta.pl/Preorder_Fast_Furious_Playset_Wrecking_Ball_Rampage_37_cm,316052,p",
                "https://yatta.pl/Preorder_Fast_Furious_Playset_Nitro_Blast_11_cm,316103,p",
                "https://yatta.pl/Star_Wars_The_Mandalorian_Model_Kit_1_72_The_Razor_Crest_34,198229,p",
                "https://yatta.pl/Star_Wars_Model_Kit_1_72_Millennium_Falcon_38_cm,184640,p",
                "https://yatta.pl/Star_Wars_Episode_VII_Model_Kit_1_52_Snowspeeder_10_cm,77972,p",
                "https://yatta.pl/Arknights_Nendoroid_More_Amiya_Extension_Set,247690,p",
                "https://yatta.pl/Preorder_The_Lord_of_the_Rings_Environment_Hobbit_Hole_Bag_E,322871,p",
                # "",


                # more than one:
                "https://yatta.pl/Vocaloid_PVC_Figure_Surprise_Nendoroid_Piapro_Characters_Ass,304021,p",
                "https://yatta.pl/Preorder_Megalomaria_Unlimited_Universe_Plastic_Model_Wrecka,321807,p",
                "https://yatta.pl/Preorder_Godzilla_x_Kong_The_New_Empire_Ultimate_Diorama_Mas,287680,p",
                "https://yatta.pl/Preorder_Godzilla_Legacy_Art_Noriyoshi_Ohrai_Statue_Heisei_G,321251,p",
                "https://yatta.pl/Preorder_Godzilla_x_Kong_The_New_Empire_Ultimate_Diorama_Mas,286020,p",
                "https://yatta.pl/Preorder_SyncyLand_Action_Figures_6_Pack_OOTD_Series_23_cm_B,321850,p",
                "https://yatta.pl/Preorder_A_Tribe_Called_Quest_ReAction_Action_Figures_3_Pack,321639,p",
                "https://yatta.pl/Preorder_My_Hero_Academia_Statue_Ultimate_Premium_Masterline,283092,p",
                "https://yatta.pl/Haikyu_PVC_Figures_Nendoroid_Surprise_Ver_02_Karasuno_Editio,304019,p",
                "https://yatta.pl/Haikyu_Nendoroid_PVC_Figures_Nendoroid_Surprise_Ver_02_Karas,294590,p",
                "https://yatta.pl/Magical_Angel_Creamy_Mami_Statue_1_1_Amazing_Vinyl_Posi_and,304608,p",
                "https://yatta.pl/Preorder_Star_Wars_Battlefront_II_Black_Series_Action_Figure,321772,p",
                "https://yatta.pl/Preorder_Disney_Classics_Legacy_Replica_Statue_1_4_Walt_Disn,320892,p",
                "https://yatta.pl/Preorder_Avatar_The_Last_Airbender_Vinyl_Figures_Appa_and_Mo,281331,p",
                "https://yatta.pl/Preorder_Predator_Sixth_Scale_Figure_Set_Thia_and_Bud_29_cm,318400,p",
                "https://yatta.pl/Yummis_Together_Plush_Figures_2_Pack_Pretzel_Beer_in_Take_Aw,292445,p",
                "https://yatta.pl/Yummis_Together_Plush_Figures_2_Pack_Burger_Fries_in_Take_Aw,292442,p",
                "https://yatta.pl/Preorder_Scott_the_Woz_Vinyl_Figures_Scott_the_Woz_Jerry_Att,292127,p",
                "https://yatta.pl/Mr_Beast_Vinyl_Figure_Glow_Panther_9_cm,263853,p",
                "https://yatta.pl/Preorder_One_Piece_Mini_Figure_5_Pack,312635,p",
                "https://yatta.pl/Preorder_Peanuts_UDF_Series_20_Mini_Figure_Charlie_Brown_Yaw,321368,p",
                "https://yatta.pl/Preorder_Universal_Monsters_Tubbz_Mini_Figure_Egg_5_cm_Blind,321680,p",
                "https://yatta.pl/Star_Wars_Model_Kit_Death_Star_II_Imperial_Star_Destroyer,198187,p",
                "https://yatta.pl/Preorder_Mighty_Morphin_Power_Rangers_Premium_Masterline_Set,318946,p",
                "https://yatta.pl/Preorder_Mighty_Morphin_Power_Rangers_Premium_Masterline_Set,318948,p",
                "https://yatta.pl/Preorder_Mighty_Morphin_Power_Rangers_Premium_Masterline_Set,318947,p",
                "https://yatta.pl/Preorder_Mighty_Morphin_Power_Rangers_Premium_Masterline_Sta,318949,p",
                "https://yatta.pl/Mystery_Mini_Blind_Box_Marvel_Thor_Ragnarok_PDQ_CDU_12,151602,p",
                "https://yatta.pl/Preorder_Silpheed_Plastic_Model_Kit_1_100_SA_77_Lancer_type,321874,p",
                "https://yatta.pl/Preorder_Halo_Campaign_Evolved_Ultimate_Premium_Masterline_S,322790,p",
                "https://yatta.pl/Preorder_Halo_Campaign_Evolved_Ultimate_Premium_Masterline_S,322791,p",
                "https://yatta.pl/Preorder_Halo_Vinyl_Figures_The_Master_Chief_Cortana_Monitor,289544,p",
                "https://yatta.pl/Preorder_Dragon_Ball_Z_Yuracolle_Series_PVC_Figures_Set_Coll,322272,p",
                "https://yatta.pl/Preorder_Reborn_Resin_Statue_1_6_Tsuna_Reborn_Natsu_37_cm,317229,p",
                "https://yatta.pl/The_Little_Prince_Figure_Little_Prince_Fox_on_the_Plane_7_cm,234055,p",
                "https://yatta.pl/Preorder_Rocky_III_Diorama_1_4_Statue_Rocky_Balboa_Apollo_Cr,286012,p",
                "https://yatta.pl/The_Smurfs_Resin_Statue_Smurfs_Column_Polychrome_Edition_50,255658,p",
                "https://yatta.pl/Preorder_Gurren_Lagann_Ultimate_Premium_Masterline_Series_St,260650,p",
                "https://yatta.pl/Preorder_Call_of_Duty_Vinyl_Figures_Ghost_Soap_Monitor_Buddi,307434,p",
                "https://yatta.pl/Preorder_Nadia_The_Secret_of_Blue_Water_Concept_Masterline_S,283273,p",
                "https://yatta.pl/Preorder_Horizon_Forbidden_West_Ultimate_Diorama_Masterline,302771,p",
                "https://yatta.pl/Preorder_Horizon_Forbidden_West_Ultimate_Diorama_Masterline,302772,p",
                "https://yatta.pl/Preorder_Breaking_Bad_Vinyl_Figure_Walt_Jesse_11_cm,234278,p",
                "https://yatta.pl/Preorder_Fullmetal_Alchemist_Concept_Masterline_Statue_1_6_R,262530,p",
                "https://yatta.pl/Preorder_Invincible_Vinyl_Figure_Invincible_vs_Conquest_12_c,283709,p",
                "https://yatta.pl/Preorder_Kuroko_s_Basket_Resin_Statue_1_6_Tetsuya_Kuroko_Tai,317231,p",
                "https://yatta.pl/Preorder_Attack_on_Titan_Ultimate_Premium_Masterline_Series,266514,p",
                "https://yatta.pl/Preorder_Avatar_The_Last_Airbender_Plush_Figure_Aang_and_Mom,234704,p",
                "https://yatta.pl/Preorder_Spirou_Fantasio_Resin_Statue_1_10_Spirou_Marsupilam,317232,p",
                "https://yatta.pl/Preorder_Seven_Deadly_Sins_Concept_Masterline_Series_Statue,242205,p",
                "https://yatta.pl/Preorder_Seven_Deadly_Sins_Concept_Masterline_Series_Statue,242206,p",
                "https://yatta.pl/Star_Wars_The_Mandalorian_Grogu_Vintage_Collection_Action_Fi,313872,p",
                "https://yatta.pl/Preorder_Lord_of_the_Rings_Mini_Figures_The_Hobbits_of_the_S,313210,p",
                # "",


                # parsing error links
                "https://yatta.pl/Preorder_Spice_and_Wolf_Merchant_Meets_the_Wise_Wolf_KDcolle,319454,p",
                "https://yatta.pl/Preorder_Spice_and_Wolf_Concept_Masterline_Series_Statue_1_5,306283,p",
                "https://yatta.pl/Harry_Potter_Snow_Globe_Hedwig_18_cm,226648,p",
                "https://yatta.pl/Preorder_Spice_and_Wolf_Merchant_Meets_the_Wise_Wolf_PVC_Sta,289968,p?over18=1",
                # "",

                # ????????
                "https://yatta.pl/Preorder_Spice_and_Wolf_Merchant_Meets_the_Wise_Wolf_PVC_Sta,289968,p?over18=1",
                "ttps://yatta.pl/Preorder_Spice_and_Wolf_Merchant_Meets_the_Wise_Wolf_PVC_Sta,289968,p"
}
KW_SKIP={"Plastic Model Kit", "Little Witch Academia", "Avatar The Last Airbender", "The Rising of the Shield Hero", "Rock Iconz", "The Last of Us", "Rainbow Six Siege",
         "The Transformers: The Movie Studio Series", "Re Zero Starting Life in Another World", "Starting Life in Another World", "Mystery Minis",
         "Teenage Mutant Ninja Turtles Ninja", "Magical Creatures", "Star Trek Generations", "Legacy", "Dragon Ball Z", "Gears of War Reloaded",
         "Grand Order", "Stay Puft", "Jason and the Argonauts", "Print Portrait", "Ganbare Douki chan", "Bobble Head", "NIJISANJI EN", "Sunshine in the Mirror",
         "Real Elite Masterline", "The Transformers The Movie Studio Series", "Aoni Production", "Rise of the Beasts", "Goddess of Victory Nikke", "Star Wars Legendary",
         "Generation One", "Godzilla vs. Kong", "Godzilla x Kong", "Shiny Colors", "Kimetsu No Yaiba", "The Mandalorian & Grogu", "One Punch Man",
         "Star Wars: Maul - Shadow Lord", "Star Wars: Ahsoka", "Jurassic World", "Fine", "Bust",  "L Size", "M Size", "S Size", "II", "Foam", "GigantiX",
         "Nendoroid", "Cafe", "LycoReco", "PVC", "Premium", "Masterline", "ED", "Ver", "Figure", "Action", "Complete", "Edition", "Skyrim", "StarCraft"
         "Bunny", "Statue", "Plush", "Vinyl", "Revenge of the Sith", "Movie", "Prop", "Taito Kuji", "Taito", "Mario Kart", "Huggy Good Smile", "Justice League"
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
         "Kadokawa", "Merchant", "Meets", "Collectoys", "StarCraft",
         }
SERIES_ALIASES = {
    # Frieren
    "frieren": "Frieren: Beyond Journey's End",
    "frieren: beyond journey´s end": "Frieren: Beyond Journey's End",
    "frieren: beyond journey's end": "Frieren: Beyond Journey's End",

    # Demon Slayer
    "demon slayer": "Demon Slayer",
    "demon slayer: kimetsu no yaiba": "Demon Slayer",

    # Wandering witch
    "journey": "Wandering Witch: The Journey of Elaina",
    "wandering witch: the journey of elaina": "Wandering Witch: The Journey of Elaina",
    # Nikke
    "goddess of victory": "Goddess of Victory",
    "goddess of victory nikke": "Goddess of Victory",
    "goddess of victory: nikke": "Goddess of Victory",

    # Evangelion
    "evangelion": "Neon Genesis Evangelion",
    "rebuild of evangelion": "Neon Genesis Evangelion",
    "neon genesis evangelion": "Neon Genesis Evangelion",

    # Honkai
    "honkai": "Honkai Impact 3rd",
    "honkai impact 3rd": "Honkai Impact 3rd",
    "honkai star rail": "Honkai: Star Rail",
    "honkai: star rail": "Honkai: Star Rail",

    # Uma Musume
    "umamusume": "Uma Musume Pretty Derby",
    "uma musume pretty derby": "Uma Musume Pretty Derby",

    # Harry potter
    "harry potter": "Harry Potter",
    "fantastic beasts": "Harry Potter",

    # My Dress-Up Darling
    "my dress up darling": "My Dress-Up Darling",
    "my dress-up darling": "My Dress-Up Darling",

    # K-On
    "k-on": "K-On!",
    "k-on!": "K-On!",

    # Hololive / VTuber
    "hololive": "Hololive Production",
    "hololive production": "Hololive Production",
    "virtual youtuber": "VTuber",
    "vtuber": "VTuber",

    # Fate
    "fate": "Fate",
    "fate series": "Fate",

    # The Witcher
    "witcher, the": "The Witcher",
    "the witcher": "The Witcher",

    # The Hobbit
    "hobbit, the": "The Hobbit",
    "the hobbit": "The Hobbit",

    # One Punch Man
    "one punch man": "One Punch Man",
    "one-punch man": "One Punch Man",

    # Spice and Wolf
    "spice & wolf": "Spice and Wolf",
    "spice and wolf": "Spice and Wolf",

    # Mushoku Tensei
    "mushoku tensei": "Mushoku Tensei: Jobless Reincarnation",
    "mushoku tensei: jobless reincarnation": "Mushoku Tensei: Jobless Reincarnation",

    # BanG Dream!
    "bang dream": "BanG Dream!",
    "bang dream!": "BanG Dream!",

    # Idolmaster
    "idolm@ster": "The Idolmaster",
    "idolmaster": "The Idolmaster",

    # Detective is Already Dead
    "detective is already dead": "The Detective is Already Dead",
    "the detective is already dead": "The Detective is Already Dead",

    # Little Armory
    "littlearmory": "Little Armory",
    "little armory": "Little Armory",

    # Monogatari
    "monogatari": "Monogatari",
    "monogatari series": "Monogatari",

    # Cyberpunk
    "cyberpunk": "Cyberpunk 2077",

    # Originals & Uncategorized
    "original character": "Original Character / Unknown",
    "original illustration": "Original Character / Unknown",
    "other": "Original Character / Unknown",

    # Vocaloid Family
    "vocaloid": "Vocaloid",
    "hatsune miku": "Vocaloid",
    "kasane teto": "Vocaloid",
    "luo tianyi": "Vocaloid",
    "racing miku": "Vocaloid",

    # === Marvel Universe ===
    "marvel": "Marvel",
    "x-men": "Marvel",
    "spider-man": "Marvel",

    # === DC Comics Universe ===
    "dc comics": "DC Comics",
    "batman": "DC Comics",
    "superman": "DC Comics",
    "wonder woman": "DC Comics",
    "justice league": "DC Comics",
    "suicide squad": "DC Comics",
    "teen titans": "DC Comics",
    "injustice": "DC Comics",

    # === Star Wars ===
    "star wars": "Star Wars",
    "original stormtrooper": "Star Wars",
    "the mandalorian": "Star Wars",
    "mandalorian": "Star Wars",
    "star wars: the clone wars": "Star Wars",
    "clone wars": "Star Wars",
    "star wars: visions": "Star Wars",
    "star wars visions": "Star Wars"

}


ua=UserAgent()
headers = {'User-Agent': ua.random}

def init_cache_from_db():
    query=db.session.query(Character.name, Series.title).join(Series, Character.S_ID == Series.S_ID).all()
    for char_name, series_title in query:
        add_to_cache(char_name, series_title)
    print(f"Loaded {len(KNOWN_CHARACTERS_LIST)} characters from the db")

def process_scraped_data(raw_results: list[dict]):
    valid_offers=[]
    failed_offers=[]

    for raw_data in raw_results:
        if not raw_data:
            continue

        if not raw_data.get("ch_name"):
            raw_data["error_reason"]="No character name"
            failed_offers.append(raw_data)
            continue

        try:
            valid_offer = ScrapedOffer.model_validate(raw_data)
            valid_offers.append(valid_offer)
        except ValidationError as ve:
            raw_data["error_reason"]="Pydantic data validation error"
            failed_offers.append(raw_data)

    if valid_offers:
        save_to_mysql(valid_offers)

    if failed_offers:
        save_failures_to_csv(failed_offers)

def save_to_mysql(valid_offers: list[ScrapedOffer]):

    for data in valid_offers:
        # first, check if such offer already exists
        offer_link = str(data.link)
        offer = db.session.query(Offer).filter_by(link=offer_link).first()
        if offer:
            offer.price = data.price
            offer.status = data.status
            continue


        # series
        title=data.series_title.strip() if data.series_title else "Original Character / Unknown"
        title_lower=title.lower()
        if title_lower in SERIES_ALIASES:
            title=SERIES_ALIASES[title_lower]
        series=db.session.query(Series).filter_by(title=title).first()
        if not series:
            series=Series(title=title)
            db.session.add(series)
            db.session.flush()


        # character
        existing_chars=db.session.query(Character).filter_by(name=data.ch_name).all()
        char=None
        if not existing_chars:
            char=Character(name=data.ch_name, S_ID=series.S_ID)
            db.session.add(char)
            db.session.flush()
        else:
            for c in existing_chars:
                if c.S_ID==series.S_ID:
                    char=c
                    break

            if not char:
                unknown_series = db.session.query(Series).filter_by(title="Original Character / Unknown").first()
                unknown_s_id=unknown_series.S_ID if unknown_series else None

                if series.title == "Original Character / Unknown" and len(existing_chars)==1:
                    char=existing_chars[0]
                elif unknown_s_id and series.title != "Original Character / Unknown":
                    char_in_unknown=next((c for c in existing_chars if c.S_ID==unknown_s_id), None)
                    if char_in_unknown:
                        char=char_in_unknown
                        char.S_ID=series.S_ID

                if not char:
                    char=Character(name=data.ch_name, S_ID=series.S_ID)
                    db.session.add(char)
                    db.session.flush()




        # figure
        fig = None
        if data.code:
            fig = db.session.query(Figure).filter_by(code=data.code).first()
        if not fig:
            fig=db.session.query(Figure).filter_by(name=data.fig_name).first()

        if not fig:
            fig=Figure(name=data.fig_name, C_ID=char.C_ID, code=data.code, manufacturer=data.manufacturer, scale=data.scale)
            db.session.add(fig)
            db.session.flush()

        new_offer=Offer(F_ID=fig.F_ID, link=offer_link, store=data.store, price=data.price, status=data.status)
        db.session.add(new_offer)

    db.session.commit()
    print(f"Saved {len(valid_offers)} offers")


def save_failures_to_csv(failed_offers: list[dict], filename="rejects.csv"):
    keys=failed_offers[0].keys()
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        writer.writerows(failed_offers)


def scrape_yatta(url="https://yatta.pl/Figurki,4,s"):
    result:list =[]

    full_link=url+"?A=0&B=80"
    resp=requests.get(full_link, headers=headers, timeout=30)

    if not resp.ok:
        print("response not ok!")
        return

    print("Extracting pg 0")
    print("response ok!")
    soup=BeautifulSoup(resp.content,"html.parser")
    result.extend(extract_page(full_link) or [])


    max_A_tag=soup.find("a", string="»")
    match = re.search(r"[?&]A=([^&]+)", max_A_tag.get("href"))
    max_A=int(match.group(1)) if match else 22


    for pg in range(1, 10):
    # for pg in range(1,16):
        time.sleep(1)
        print(f"Extracting page {pg}")
        full_link=f"{url}?A={pg}&B=80"

        if resp.ok:
            print("response ok!")
            result.extend(extract_page(full_link) or [])
        else:
            print(f"HTTP error: {resp.status_code}, at pg: {pg}")

    print(f"Finished scraping. Found {len(result)} potential offers")
    process_scraped_data(result)

def extract_page(link):
    resp=requests.get(link, headers=headers, timeout=30)
    soup=BeautifulSoup(resp.content,"html.parser")

    products=soup.find_all("div", {"id": "product_container_large"})
    result: list =[]
    for product in products:
        time.sleep(1)
        current=product.find("a")
        link="https:"+current.get("href")
        if link in URL_BLACKLIST:
            print("rejected - url blacklisted!")
            continue
        ext_data=extract(link)
        if ext_data:
            result.append(ext_data)
            print("current figure:")
            print(ext_data["link"])
            print()
            print("current character name")
            print(ext_data["ch_name"])
            print()
            print("missing attrs:")
            for k, v in ext_data.items():
                if not v:
                    print(k)
            print()
            print()
            print()
        else:
            print("figure")
            print(link)
            print()
            print()
        # to delete:
        # break


    # print("extracting links")
    return result

def extract(link: str):
    # print("hello from extractor")
    try:
        resp=requests.get(link, headers=headers, timeout=30)
        resp.raise_for_status()
    except RequestException as err:
        print(f"Error while connecting to {link}")
        return None
    if not resp.ok:
        print("response not ok!")
        return None
    soup=BeautifulSoup(resp.content,"html.parser")
    res :dict[str, Any]= {
        'fig_name': None,
        'price': None,
        'link': link,
        'code': None,
        'series_title': None,
        'manufacturer': None,
        'status': StatusEnum.AVAILABLE,
        'scale': None,
        'store': StoreEnum.YATTA,
        'ch_name': None,
    }

    # interesting_part=soup.find("div", style="margin-top:10px;")
    # print(interesting_part.get_text())

    raw_title = soup.find("h2", class_="tytul").get_text()
    fig_name = re.sub(r'\s+', ' ', raw_title).strip()
    if fig_name:
        res['fig_name']=fig_name
    # print(fig_name)
    if any(word in fig_name.lower() for word in KW_BLACKLIST):
        res['fig_name']=None
        res['link']=link
        print("blacklisted fig name - returning empty name")
        return res

    price_node=soup.find(string=re.compile("Cena:"))
    if price_node:
        price_tag=price_node.find_next("span")
        if price_tag:
            try:
                price=Decimal(price_tag.get("content"))
                res['price']=price
            except InvalidOperation:
                pass



    res['link']=link



    code_node = soup.find(string=re.compile("ISBN:"))
    if code_node:
        code = code_node.split(':')[1].strip()
        res['code']=code
        # print(code)



    series_node = soup.find(string=re.compile("Seria:"))
    if series_node:
        series_tag = series_node.find_next_sibling("a")
        if series_tag:
            series_name = series_tag.text.strip()
            series_name_lower = series_name.lower()
            if series_name_lower in SERIES_ALIASES:
                series_name = SERIES_ALIASES[series_name_lower]
            res['series_title']=series_name
            # print(series_name)



    manuf_node=soup.find(string=re.compile(r"Producent:|Wydawca:"))
    if manuf_node:
        manuf_tag=manuf_node.find_next_sibling("a")
        if manuf_tag:
            manufacturer=manuf_tag.text.strip()
            res['manufacturer']=manufacturer
            # print(manufacturer)



    status=StatusEnum.AVAILABLE
    if "Preorder" in fig_name:
        status=StatusEnum.PREORDER
        res['fig_name']=fig_name.replace("Preorder:", "").strip()

    else:
        unav=soup.find(string=re.compile("brak towaru"))
        if unav:
            status=StatusEnum.UNAVAILABLE
    res["status"]=status
    # print(status)


    store=StoreEnum.YATTA
    res['store']=store


    code=res.get("code")
    name=""
    scale=""
    series_title=res.get("series_title", "")
    desc = soup.find("div", itemprop="description")
    desc_text = desc.get_text(separator='\n', strip=True).replace('\xa0', ' ') if desc else ""




    name, is_fallback=get_name_from_cache(fig_name, series_title)
    if name and not is_fallback:
        print("found name locally")

    match = re.search(r"1/\d+", fig_name + ' ' + desc_text)
    if not match:
        match = re.search(r'\d+\s*cm', fig_name + ' ' + desc_text, re.IGNORECASE)
    scale = match.group(0) if match else ""


    if code and (not name or not scale or is_fallback):
            mfc_char, mfc_scale=get_name_from_MFC(code)
            if not name and mfc_char:
                name=mfc_char
                is_fallback=False
            if not scale and mfc_scale:
                scale=mfc_scale

    if not name or is_fallback:
        fig_strp=fig_name
        if res.get("series_title"):
            fig_strp=fig_strp.replace(res.get("series_title"),"").strip()
        if res.get("manufacturer"):
            fig_strp=fig_strp.replace(res.get("manufacturer"),"").strip()
        fig_strp=re.sub(r'[^a-zA-Z0-9/\- ]', "", fig_strp).strip()
        # print(fig_strp)

        if fig_strp and desc_text:
            desc_name, desc_is_fallback=get_name_from_desc(fig_strp, desc_text, series_title)
            if desc_name and not desc_is_fallback:
                name=desc_name
            elif desc_name and desc_is_fallback and not name:
                name=desc_name
    # print(name)
    res["scale"] = scale

    if not name:
        print("could not extract the character name for this figure")
        return res
    else:
        res["ch_name"]=name
        add_to_cache(name, res.get("series_title", ""))






    return res

def add_to_cache(name: str, series_title: str):
    if not name:
        return

    if name not in KNOWN_CHARACTERS_DICT:
        KNOWN_CHARACTERS_DICT[name]=set()

        inserted=False
        for i, char in enumerate(KNOWN_CHARACTERS_LIST):
            if len(name) > len(char):
                KNOWN_CHARACTERS_LIST.insert(i, name)
                inserted=True
                break
        if not inserted:
            KNOWN_CHARACTERS_LIST.append(name)

    if series_title:
        KNOWN_CHARACTERS_DICT[name].add(series_title.lower())

def get_name_from_cache(fig_name: str, series_title=""):
    fallback_name=None
    series_lower=series_title.lower() if series_title else ""

    for char_name in KNOWN_CHARACTERS_LIST:
        match=False
        if re.search(rf'\b{re.escape(char_name)}\b', fig_name, re.IGNORECASE):
            match=True
        else:
            words = char_name.split(' ')
            if len(words) == 2:
                inverted = f"{words[1]} {words[0]}"
                if re.search(rf'\b{re.escape(inverted)}\b', fig_name, re.IGNORECASE):
                    match=True

        if match:
            known_series = KNOWN_CHARACTERS_DICT.get(char_name, set())
            if series_lower and series_lower != "original character / unknown":
                if series_lower not in known_series and "original character / unknown" not in known_series:
                    continue  # Ignorujemy i szukamy dalej

            if series_lower and (char_name.lower() in series_lower or series_lower in char_name.lower()):
                if not fallback_name:
                    fallback_name=char_name
                continue
            return char_name, False
    return fallback_name, True


def get_name_from_desc(fig_strp, desc, series_title=""):
    fallback_name=None
    series_lower=series_title.lower() if series_title else ""

    combined_text = f"{fig_strp}. {desc}"
    patterns = [
        r"(?:[Nn]endoroid|[Ff]igma)\s+([A-Z][a-zA-Z\-]+(?:\s[A-Z][a-zA-Z\-]+)?)",
        r"(?:[Nn]endoroid|[Ff]igure|[Ss]tatue|[Ff]igma)\s+(?:of|is)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",
        r"[Pp]resenting\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",
        r"[Cc]omes\s+a\s+.*?\s+of\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",
        r"[Cc]omes\s+([A-Z][a-z\-]+(?:\s[A-Z][a-z\-]+)?)",
        r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+from\s+the",
        r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+arrives",
        r"[Oo]riginal\s+[Cc]haracter\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",
        r"[\"']?([A-Z][a-z\-]+(?:\s[A-Z][a-z\-]+)?)[\"']?\s+is\s+now\s+available",
        r"(?:worn|used|wielded)\s+by\s+([A-Z][a-z\-]+(?:\s[A-Z][a-z\-]+)?)",
        r"figure\s+of\s+(?:the\s+)?(?:[0-9a-zA-Z\-]+\s+)?([A-Z][a-z\-]+(?:\s[A-Z][a-z\-]+)?)",
        r"illustration,\s*([A-Z][a-zA-Z\s]+?),\s*(?:comes\s+to\s+life|as\s+a)",
        r"(?:[Ff]igure|1/\d+|[Kk]it|[Bb]ust)\s+([A-Z][a-zA-Z\s]+?)\s+\d+\s*cm"
    ]
    for pattern in patterns:
        match = re.search(pattern, combined_text)
        if match:
            extracted_name=match.group(1).strip()
            contains_skip=False
            for banned in KW_SKIP:
                if re.search(rf"\b{re.escape(banned)}\b", extracted_name, re.IGNORECASE):
                    contains_skip=True
                    break

            if contains_skip:
                continue

            if any(part in fig_strp for part in extracted_name.split()):
                if series_lower and (extracted_name.lower() in series_lower or series_lower in extracted_name.lower()):
                    if not fallback_name:
                        fallback_name=extracted_name
                    continue
                return extracted_name, False

    clean_fig_strip=fig_strp
    for banned in KW_SKIP:
        clean_fig_strip=re.sub(rf"\b{re.escape(banned)}\b", "", clean_fig_strip, flags=re.IGNORECASE)

    fig_split=clean_fig_strip.split(" ")
    name=[]
    for word in fig_split:
        if not word or not word[0].isupper():
            continue

        if re.search(rf'\b{re.escape(word)}\b', desc, re.IGNORECASE):
            name.append(word)
    carved_name=" ".join(name)
    if carved_name:
        if series_lower and (carved_name.lower() in series_lower or series_lower in carved_name.lower()):
            if not fallback_name:
                fallback_name=carved_name
        else:
            return carved_name, False
    return fallback_name, True

def get_name_from_MFC(code):
    url = f"https://myfigurecollection.net/browse.v4.php?barcode={code}"
    time.sleep(1)
    hd = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    resp = requests.get(url, headers=headers, timeout=60)
    if not resp.ok:
        print("response not ok!")
        print(f"error while assessing {code}")
        return "", ""


    if "/item/" not in resp.url:
        print("no such code or invalid code")
        return "", ""
    soup=BeautifulSoup(resp.content,"html.parser")


    char=""
    char_label = soup.find("div", class_="data-label", string=re.compile("Character"))
    if char_label:
        char_value=char_label.find_next_sibling("div", class_="data-value")
        if char_value:
            char_tag=char_value.find("a")
            if char_tag:
                char=char_tag.text.strip()
    if char:
        print("found character name on MFC!")
    scale=""
    scale_tag=soup.find("a", class_="item-scale")
    if scale_tag:
        scale=scale_tag.text.strip()
    return char, scale


# extract_page("https://yatta.pl/Figurki,4,s?A=0&B=80")

