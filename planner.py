"""Full-featured itinerary planner with real activities, hotels, and restaurants."""
from __future__ import annotations
from budget import calculate_budget

CITY_STOPS = {
    "Jaipur": [
        {
            "morning": "Amber Fort — arrive at 8am opening. Allow 2.5 hours for Sheesh Mahal, Diwan-e-Aam, and Ganesh Pol. Hire a guide at the gate (₹300) for historical context.",
            "afternoon": "City Palace Museum + Jantar Mantar cluster. Walk to Hawa Mahal for exterior photos (15 min). Johari Bazaar for silver jewellery and bangles.",
            "evening": "LMB (Laxmi Misthan Bhandar) in Johari Bazaar for raj kachori and sweets. Then Nahargarh Fort for sunset panorama (30 min drive). Optional: return for Amber Light & Sound Show (7:30pm, ₹295).",
            "recommended_hotel_budget": "Zostel Jaipur (₹450/dorm, ₹1200/private) — MI Road, near food and transport",
            "recommended_hotel_mid": "Pearl Palace Heritage (₹2800, free breakfast + airport pickup) — Hathroi area",
            "recommended_hotel_luxury": "Jai Mahal Palace (₹12,000+) — Civil Lines, palatial heritage property",
            "must_eat": "Morning: Tapri Central (masala chai + kachori, 8am). Lunch: LMB (raj kachori ₹120, thali ₹280). Evening: Chokhi Dhani (cultural dinner ₹900 inclusive)",
        },
        {
            "morning": "Galtaji (Monkey Temple) at dawn — natural gorge temple with langur monkeys. Then Albert Hall Museum (Jaipur's state museum, ₹150).",
            "afternoon": "Patrika Gate + Jawahar Circle park. Bapu Bazaar for block-print textiles and blue pottery shopping.",
            "evening": "Nahargarh Fort sunset + rooftop Padao restaurant (beer/cocktails with city views). Return for dinner at a local dhaba near MI Road.",
            "recommended_hotel_budget": "Zostel Jaipur",
            "recommended_hotel_mid": "Pearl Palace Heritage",
            "recommended_hotel_luxury": "Rambagh Palace (₹25,000+, former royal residence)",
            "must_eat": "Breakfast at Lassiwala (Old MI Road, open 8am) for pure cream lassi. Lunch at Rawat Mishthan (Sindhi Camp, pyaaz kachori ₹20). Dinner: LMB thali.",
        },
    ],
    "Udaipur": [
        {
            "morning": "City Palace Museum — open 9:30am, allow 2 hours. Visit Crystal Gallery (₹750, extraordinary). Then Jagdish Temple below (free, 7am-2pm, 4pm-10pm).",
            "afternoon": "Lake Pichola boat ride from Rameshwar Ghat (₹400, 1 hour). Stops include exterior view of Taj Lake Palace. Then walk Bagore ki Haveli area.",
            "evening": "Sunset dinner at Ambrai Restaurant — lakeside table with City Palace view (book in advance). Walk old city lanes after dark.",
            "recommended_hotel_budget": "Krishna Niwas Guest House (₹700, lake view rooftop, Jagdish Temple area)",
            "recommended_hotel_mid": "Amet Haveli (₹4500, right on lake) or Lake Pichola Hotel (₹3800)",
            "recommended_hotel_luxury": "Taj Lake Palace (₹35,000+, island hotel) or Fateh Prakash Palace (₹18,000, inside City Palace)",
            "must_eat": "Breakfast: rooftop cafe at Krishna Niwas or Cafe Edelweiss (German bakery, near Jagdish Temple). Lunch: Natraj Dining Hall (unlimited thali ₹180). Dinner: Ambrai (₹800/person, lake views)",
        },
        {
            "morning": "Saheliyon Ki Bari (Garden of Maids, ₹50) at opening. Then Shilpgram Crafts Village (₹30) for Rajasthani artisans.",
            "afternoon": "Fateh Sagar Lake promenade — boat rides, street food, cycling. Moti Magri hill for Maharana Pratap statue and lake panorama.",
            "evening": "Bagore ki Haveli cultural dance performance (7pm, ₹60). Then dinner in old city — Jheel Guest House rooftop or Millets of Mewar (health-conscious).",
            "recommended_hotel_budget": "Krishna Niwas Guest House",
            "recommended_hotel_mid": "Amet Haveli or Jagat Niwas Palace Hotel",
            "recommended_hotel_luxury": "Oberoi Udaivilas (₹45,000+) or Taj Lake Palace",
            "must_eat": "Breakfast: Cafe 1559 AD (inside Haveli). Lunch: Upre by 1559 AD (lake view rooftop). Dinner: Millets of Mewar (healthy local food)",
        },
    ],
    "Jodhpur": [
        {
            "morning": "Mehrangarh Fort — open 9am, buy audio guide (₹200, narrated by Maharaja + Prince Charles). Allow 3 hours for all 7 museum galleries. Optional: Flying Fox zipline (₹2000).",
            "afternoon": "Jaswant Thada (white marble cenotaph, ₹30, stunning). Then Toorji Ka Jhalra stepwell (free, best for photography 2-4pm). Rao Jodha Desert Rock Park (₹100, 1 hour).",
            "evening": "Clock Tower Sardar Market food walk — Mishrilal's makhaniya lassi (₹80, UNMISSABLE). Pyaaz kachori from the market. Dinner at Indique rooftop restaurant (₹900/person, fort views, reserve table).",
            "recommended_hotel_budget": "Zostel Jodhpur (₹500 dorm, fort views, Old City)",
            "recommended_hotel_mid": "Haveli Inn Pal (₹3500, heritage haveli, old city)",
            "recommended_hotel_luxury": "RAAS Jodhpur (₹16,000, at foot of fort, award-winning)",
            "must_eat": "Breakfast: Jhankar Choti Haveli rooftop (₹300, fort views). Lunch: Gypsy Restaurant (Blue City views). Evening: Mishrilal's lassi + market snacks. Dinner: Indique",
        },
        {
            "morning": "Blue City heritage walk — 7am, before heat. Hire a walking guide from Zostel or local operators (₹500). Explore lanes below the fort.",
            "afternoon": "Umaid Bhawan Palace Museum (₹100) — still a royal residence, museum in one wing. Kailana Lake for a relaxed afternoon boat ride.",
            "evening": "Rooftop dinner in Old City — multiple options with fort views. Try local dal baati churma at a traditional restaurant.",
            "recommended_hotel_budget": "Zostel Jodhpur",
            "recommended_hotel_mid": "Hotel Ghoomar (₹2800) or Ratan Vilas (₹3200)",
            "recommended_hotel_luxury": "RAAS Jodhpur or Vivanta Jodhpur (₹8000+)",
            "must_eat": "Breakfast: Shri Mishrilal kachori (7am, Clock Tower). Lunch: Gypsy Restaurant or local dhaba. Dinner: Chokelao Garden restaurant inside Mehrangarh (₹1200, heritage setting)",
        },
    ],
    "Jaisalmer": [
        {
            "morning": "Jaisalmer Fort at sunrise — 6am start. Walk the fort lanes as the golden stone glows amber. Visit Jain Temples inside fort (free, opens 7am). Raj Mahal palace (₹70).",
            "afternoon": "Patwon Ki Haveli (₹100, most ornate haveli, 10am-5pm). Gadisar Lake (free, 30 min, beautiful reflection photography). Sunset walk on fort ramparts.",
            "evening": "Trio Restaurant for dinner (fort view rooftop, ker sangri + camel milk kulfi). Arrange next day desert safari.",
            "recommended_hotel_budget": "Hotel Oasis (₹900, old city, fort views, travel desk)",
            "recommended_hotel_mid": "Desert Haveli Guest House (₹2200, inside fort, atmospheric)",
            "recommended_hotel_luxury": "Suryagarh Palace (₹22,000, Sam Road, award-winning desert experience)",
            "must_eat": "Breakfast: rooftop cafe inside fort. Lunch: Desert Boy's Dhani (₹200, authentic). Dinner: Trio Restaurant (₹600/person, best fort views)",
        },
        {
            "morning": "Slow start — explore fort at your pace, rooftop breakfast with golden light. Visit artisan workshops inside fort for textiles and mirror-work.",
            "afternoon": "Transfer to Sam Sand Dunes (40km, 1 hour by arranged jeep). Check in to camp. Afternoon tea and orientation.",
            "evening": "Camel safari at sunset (1.5 hours on dunes). Folk music performance at camp. Dinner under stars. Star gazing — Jaisalmer has some of India's darkest skies.",
            "recommended_hotel_budget": "Budget desert camp (₹1500-2000 all inclusive, Sam Dunes)",
            "recommended_hotel_mid": "Mid-range camp like Manvar Desert Camp (₹4000-6000 all inclusive)",
            "recommended_hotel_luxury": "Suryagarh Palace or The Serai (₹15,000+, luxury camps near Sam)",
            "must_eat": "Camp dinner (included in package, Rajasthani thali). Morning at Sam: chai and parathas before sunrise walk on empty dunes.",
        },
    ],
    "Ranthambore": [
        {
            "morning": "Morning safari — report at park gate 6:15am for 6:30am departure. 3.5-hour game drive in booked zone. Best chance of tiger sighting. Zones 1-5 preferred.",
            "afternoon": "Return to hotel by 10am. Hot breakfast. Rest (essential for early start). Review morning sightings with naturalist. Optional: Ranthambore Fort visit (2pm, requires park permit, inside park).",
            "evening": "Sunset at Padam Talao lake viewpoint if staying near Zone 3. Early dinner and early sleep for next morning safari.",
            "recommended_hotel_budget": "RTDC Vinayak Tourist Complex (₹1500, government property, near park gate)",
            "recommended_hotel_mid": "Hotel Hammir (₹3500, Ranthambore Road, breakfast included, safari desk)",
            "recommended_hotel_luxury": "Sher Bagh Luxury Tented Camp (₹28,000/person all-inclusive, adjacent to park zones 1-4)",
            "must_eat": "Pre-safari: light hotel breakfast (hotel packs sandwiches for jeep). Post-safari: hot breakfast at hotel. Lunch: hotel restaurant or Ranthambore Road local dhabas. Dinner: hotel (limited options in area).",
        },
    ],
    "Pushkar": [
        {
            "morning": "Brahma Temple — visit 6:30am for morning arti (powerful spiritual experience). Then Pushkar Lake Ghats — walk all 52 ghats barefoot at sunrise. Avoid Brahmin priests pushing paid puja rituals.",
            "afternoon": "Pushkar market — one of Rajasthan's best. Tie-dye fabrics, camel leather, silver jewellery, and traditional instruments. Savitri Temple cable car (₹85, summit views).",
            "evening": "Evening arti at the ghats (7pm). Dinner on a rooftop watching the town lights. Pushkar is alcohol-free and fully vegetarian.",
            "recommended_hotel_budget": "Hotel Everest (₹800, clean, central) or Zostel Pushkar (₹450 dorm)",
            "recommended_hotel_mid": "Bhanwar Singh Palace (₹3200, lake views, yoga terrace)",
            "recommended_hotel_luxury": "The Westin Pushkar Resort (₹12,000, outside town, luxury pool)",
            "must_eat": "Breakfast: Om Shiva Garden Restaurant (rooftop, lake view, pancakes and Israeli breakfast). Lunch: Raju's Restaurant (falafel, shakshuka ₹250). Dinner: Sunset Cafe or Park Restaurant (rooftop, thali ₹300). Note: 100% vegetarian town, no alcohol.",
        },
    ],
    "Mount Abu": [
        {
            "morning": "Dilwara Jain Temples — open noon so use morning for Guru Shikhar (1722m, highest point in Rajasthan, 30km drive). Views of Gujarat and Rajasthan on a clear day.",
            "afternoon": "Dilwara Temples (noon-6pm) — take your full time for 5 temples. The marble carvings rival the Taj Mahal. No photography — experience it fully.",
            "evening": "Sunset Point (Honeymoon Point) at Nakki Lake. Boat ride on Nakki Lake (₹50/person). Mount Abu market for local wool shawls and Rajput artefacts.",
            "recommended_hotel_budget": "Hotel Lake Palace (₹1200, near Nakki Lake)",
            "recommended_hotel_mid": "Hilltone Hotel (₹4500, pool, Aravalli views)",
            "recommended_hotel_luxury": "Palace Hotel (Bikaner House, ₹8000, heritage property of Bikaner royal family)",
            "must_eat": "Breakfast: Cafe Shikhar (panoramic views). Lunch: Kesar Restaurant (₹300, Gujarati-Rajasthani thali). Evening: Chacha Museum Cafe (quirky local spot). Dinner: Arbuda Restaurant (₹500, good variety).",
        },
    ],
    "Bikaner": [
        {
            "morning": "Junagarh Fort (9:30am-4:30pm, ₹100+₹50 camera). Unlike most Rajasthan forts, never been conquered. 37 palaces and temples inside. Museum has WWII-era biplanes and royal palanquins.",
            "afternoon": "Karni Mata Temple (Rat Temple, 30km, ₹0 entry) — controversial but culturally fascinating. Over 20,000 rats revered as reincarnations of devotees. Or: old city haveli walk (Rampuria Havelis cluster).",
            "evening": "Bikaner is famous for Bikaneri bhujia — buy direct from Haldiram's (original Bikaner branch). Local kulfi and sweets from old city markets.",
            "recommended_hotel_budget": "Hotel Sagar (₹1200, central)",
            "recommended_hotel_mid": "Hotel Bhanwar Niwas (₹3500, heritage haveli, old city)",
            "recommended_hotel_luxury": "Laxmi Niwas Palace (₹8000, royal heritage, camel polo ground)",
            "must_eat": "Morning: Laxmi Narayan Tea stall (local chai culture). Lunch: Vino Restaurant (₹250, local Bikaneri food). Must try: Bikaneri bhujia, rasgulla, mawa kachori. Dinner: Gallops Restaurant (₹400, rooftop).",
        },
    ],
    "Bundi": [
        {
            "morning": "Taragarh Fort (Bundi) — spectacular hilltop fort with wild monkeys, overgrown palaces, and sweeping views. Allow 2 hours, go early. Bundi Palace below (₹100, extraordinary frescoes).",
            "afternoon": "Nawal Sagar Lake reflections. Bundi stepwells walk — Raniji ki Baori (Queen's stepwell, free, most beautiful in Rajasthan). 84-pillar cenotaph.",
            "evening": "Old city walks — Bundi is one of Rajasthan's most atmospheric and least touristy towns. Murals cover the old city walls. Simple dinner at local guesthouse.",
            "recommended_hotel_budget": "Haveli Braj Bhushanjee (₹1000-3000, 200-year-old haveli, famous for painted walls)",
            "recommended_hotel_mid": "Bundi Vilas (₹4000, fort views)",
            "recommended_hotel_luxury": "Ishwari Niwas Palace (₹7000)",
            "must_eat": "Breakfast: rooftop guesthouse. Lunch: Restaurants near bus stand (₹150 thali). Dinner: guesthouse — Bundi has very limited restaurant options, most travellers eat where they sleep.",
        },
    ],
    "Sawai Madhopur": [
        {
            "morning": "Safari as above (see Ranthambore). Sawai Madhopur town has a small bazaar for local Rajasthani snacks post-safari.",
            "afternoon": "Rest. Optional: Ranthambore Fort inside the park (UNESCO candidate, requires zone entry, ask your naturalist about timing).",
            "evening": "Dusk at the Padam Talao lake area if your zone permits. Early dinner and early sleep.",
            "recommended_hotel_budget": "RTDC Vinayak (₹1500) or Tiger Den Resort (₹2000)",
            "recommended_hotel_mid": "Hotel Hammir (₹3500) or Khem Villas (₹5000)",
            "recommended_hotel_luxury": "Sher Bagh (₹28,000 all-inclusive) or Aman-i-Khas (₹65,000+, ultra-luxury)",
            "must_eat": "Pre-safari: hotel packed breakfast. Post-safari: hotel restaurant. Local area: Ranthambore Road dhabas for simple Rajasthani meals.",
        },
    ],
    "Chittorgarh": [
        {
            "morning": "Chittorgarh Fort — UNESCO World Heritage Site, India's largest fort (700 acres). Start at 8am. Vijay Stambha (Victory Tower), Kirti Stambha, Rana Kumbha Palace, Padmini Palace and lake.",
            "afternoon": "Meera Temple and Kumbha Shyam temple cluster. The fort is massive — hire a guide or jeep inside (₹300) to cover all sites.",
            "evening": "Light and Sound Show (₹100, 7:30pm, spectacular in the fort setting). Stay the night in Chittorgarh town.",
            "recommended_hotel_budget": "Hotel Chetak (₹900)",
            "recommended_hotel_mid": "Padmini Palace Hotel (₹3500, fort views)",
            "recommended_hotel_luxury": "Castle Bijaipur (₹8000, 16th century castle near Chittorgarh)",
            "must_eat": "Breakfast: hotel. Lunch: local dhaba in town (₹150 thali). Dinner: hotel restaurant (limited options).",
        },
    ],
    "Kumbhalgarh": [
        {
            "morning": "Kumbhalgarh Fort (UNESCO Heritage, ₹100 Indian, ₹600 foreigner, 9am-6pm) — home of the second longest wall in the world after Great Wall of China (36km). 360 temples inside.",
            "afternoon": "Kumbhalgarh Wildlife Sanctuary — wolf, leopard, sloth bear habitat. Evening drive inside sanctuary (arrange at hotel).",
            "evening": "Light and Sound Show (7:30pm, ₹100). Quiet night in a heritage property near the fort.",
            "recommended_hotel_budget": "Kumbhal Castle Resort (₹2000)",
            "recommended_hotel_mid": "Fateh Safari Lodge (₹5000)",
            "recommended_hotel_luxury": "Aodhi Hotel by HRH (₹12,000, royal hunting lodge converted)",
            "must_eat": "Hotel meals (limited options in area). Pack snacks for fort walk.",
        },
    ],
    "Bharatpur": [
        {
            "morning": "Keoladeo Ghana National Park (UNESCO, ₹50 Indians, ₹500 foreigners). Best birding in India. Hire a cycle rickshaw inside (₹150/hour). Over 230 resident and 130 migratory bird species.",
            "afternoon": "Deeg Palace (45km, ₹200) — rarely visited but extraordinary water palace with 2000+ fountains. Or: Bharatpur Fort.",
            "evening": "Return. Bharatpur is often a transit stop for Agra (55km) — convenient base for both.",
            "recommended_hotel_budget": "RTDC Saras Tourist Bungalow (₹1500, inside park buffer zone)",
            "recommended_hotel_mid": "Laxmi Vilas Palace (₹4500, heritage)",
            "recommended_hotel_luxury": "The Bagh (₹8000, heritage garden property)",
            "must_eat": "Hotel meals. Park canteen for basic snacks.",
        },
    ],
    "Shekhawati": [
        {
            "morning": "Mandawa town — open-air fresco gallery. Hundreds of painted havelis line the streets, most with doors open. Mandawa Fort (hotel now). 3-hour walk covers the main painted havelis.",
            "afternoon": "Nawalgarh (30km) — the other great Shekhawati fresco town. Poddar Haveli Museum (₹50) has 750 rooms of painted walls.",
            "evening": "Castle Mandawa (heritage hotel) for dinner. Shekhawati at sunset with painted walls glowing is magical.",
            "recommended_hotel_budget": "Shekawati Guest House (₹1200, Nawalgarh)",
            "recommended_hotel_mid": "Apani Dhani (₹3500, eco-village, Nawalgarh)",
            "recommended_hotel_luxury": "Castle Mandawa (₹8000, converted fort)",
            "must_eat": "Breakfast: hotel. Lunch: local thali in Mandawa market (₹150). Dinner: Castle Mandawa restaurant or Nawalgarh guesthouse.",
        },
    ],
    "Alwar": [
        {
            "morning": "Sariska Tiger Reserve — book safari online (sariskatigerreserve.in). Less famous than Ranthambore but recovering tiger population. Morning safari 6:30am.",
            "afternoon": "Alwar City Palace (museum, ₹50). Bala Qila fort above city (jeep recommended).",
            "evening": "Siliserh Lake Palace — sunset on the lake (lake palace now a heritage hotel, visit for tea).",
            "recommended_hotel_budget": "Hotel Aravali (₹1500)",
            "recommended_hotel_mid": "Sariska Palace (₹4000, heritage)",
            "recommended_hotel_luxury": "Sariska Tiger Camp (₹8000)",
            "must_eat": "Local Alwar milk cake (Alwar ka Mawa) — famous throughout Rajasthan. Available from Thana Sweet Shop.",
        },
    ],
    "Barmer": [
        {
            "morning": "Kiradu temples — 5 Somnatha-style temples from 11th century, partially restored. Intricate carvings, remote location, mystical atmosphere.",
            "afternoon": "Barmer old city havelis and textile market — famous for Barmer block printing and applique work. Buy directly from artisans.",
            "evening": "Desert landscape exploration near Barmer — remote Thar experience without Sam Dunes crowds.",
            "recommended_hotel_budget": "Hotel Krishna Palace (₹1200)",
            "recommended_hotel_mid": "Hotel Kiran (₹2500)",
            "recommended_hotel_luxury": "Rawla Narlai (₹7000, 90 min from Barmer, leopard safari)",
            "must_eat": "Local Marwari thali. Barmer is an authentic working town — eat where locals eat near the bus stand.",
        },
    ],
    "Osian": [
        {
            "morning": "Osian temple complex — 18 Brahmin and Jain temples from 8th-12th centuries, largely intact and rarely visited. Sachiya Mata Temple (active pilgrimage site).",
            "afternoon": "Osian sand dunes (mini desert experience without Sam Dunes crowds). Camel ride and sunset photography.",
            "evening": "Return to Jodhpur (65km) or overnight at a desert camp.",
            "recommended_hotel_budget": "Osian Camel Camp (₹2000, basic tents)",
            "recommended_hotel_mid": "Osian Safari Camp (₹5000)",
            "recommended_hotel_luxury": "Return to RAAS Jodhpur",
            "must_eat": "Simple local meals. Osian has very limited restaurant options.",
        },
    ],
    "Nathdwara": [
        {
            "morning": "Shrinathji Temple (Srinathji, one of the holiest Vaishnava temples). Darshan requires patience — queues can be 2+ hours. Go for 5:30am Mangala darshan if you can.",
            "afternoon": "Pichwai painting workshops — Nathdwara is the center of this distinctive cloth-painting tradition. Visit artists' studios and buy directly.",
            "evening": "Rajsamand Lake (8km) — beautiful lake built 1662 AD with marble embankment and 9 chhatris.",
            "recommended_hotel_budget": "Hotel Shreenath (₹800, near temple)",
            "recommended_hotel_mid": "Nath Resort (₹3000)",
            "recommended_hotel_luxury": "Return to Udaipur (45km) for luxury stays",
            "must_eat": "Temple prasad (offered to all devotees). Local Rajasthani thali in bazaar.",
        },
    ],
    "Kota": [
        {
            "morning": "Kota Garh (City Palace Museum, ₹100) — powerful Kota School miniature paintings. The best collection of this distinct style outside Delhi.",
            "afternoon": "Chambal River Boat Ride (₹200/person) — gharial crocodiles, river dolphins, birds. Book at the ghats.",
            "evening": "Kishore Sagar Lake and Jagmandir Island. Brij Vilas Palace museum.",
            "recommended_hotel_budget": "Hotel Navrang (₹1200)",
            "recommended_hotel_mid": "Palkiya Haveli (₹3500, heritage)",
            "recommended_hotel_luxury": "Umed Bhawan Palace (₹8000, heritage, Kota royal family)",
            "must_eat": "Kota kachori (different from Jodhpur — sweeter). Kota ke badi (dal dumplings). Kedarnath Mishthan Bhandar for sweets.",
        },
    ],
    "Dungarpur": [
        {
            "morning": "Juna Mahal (one of Rajasthan's oldest and least-visited palaces, 13th century, extraordinary murals). Gaib Sagar Lake.",
            "afternoon": "Udai Bilas Palace (now a heritage hotel — visit for tea if not staying). Local tribal craft exploration.",
            "evening": "Quiet South Rajasthan town feel — very different from the tourist circuit.",
            "recommended_hotel_budget": "Hotel Sunrise (₹1000)",
            "recommended_hotel_mid": "Udai Bilas Palace (₹7000, heritage hotel on lake)",
            "recommended_hotel_luxury": "Udai Bilas Palace",
            "must_eat": "Local Wagad region cuisine — different from mainstream Rajasthani food. Try local maize rotis and tribal preparations.",
        },
    ],
    "Jhalawar": [
        {
            "morning": "Gagron Fort (UNESCO, ₹100) — water fort at confluence of two rivers. One of Rajasthan's most distinctive forts.",
            "afternoon": "Jhalawar Archaeological Museum (₹10). Local Buddhist caves at Kolvi (30km).",
            "evening": "Quiet evening in an authentic small Rajasthani town.",
            "recommended_hotel_budget": "Hotel Chandrawati (₹900)",
            "recommended_hotel_mid": "Heritage Hotel Jhalawar (₹2500)",
            "recommended_hotel_luxury": "Return to Kota or Bundi",
            "must_eat": "Local Rajasthani food at market area dhabas.",
        },
    ],
    "Sikar": [
        {
            "morning": "Fatehpur Shekhawati (30km) — the finest concentration of painted havelis in Rajasthan. Nadine Le Prince Cultural Centre (French artist restored a haveli, free).",
            "afternoon": "Sikar city's Gopinath and Madan Mohan havelis. Local textile market.",
            "evening": "Gateway to main Shekhawati circuit — continue to Mandawa or Nawalgarh.",
            "recommended_hotel_budget": "Hotel Sikar Inn (₹1200)",
            "recommended_hotel_mid": "Piramal Haveli (₹5000, beautifully restored)",
            "recommended_hotel_luxury": "Piramal Haveli",
            "must_eat": "Local Marwari cuisine. Shekhawati region known for kesar peda, churma, and rabri.",
        },
    ],
    "Tonk": [
        {
            "morning": "Sunehri Kothi (the Golden Mansion — extraordinary interior with gold and mirror work, free to visit). Arabic and Persian Manuscript Library.",
            "afternoon": "Bisaldeo Temple (8th century, carved sandstone). Local qawwali music scene (Tonk has a significant Muslim heritage).",
            "evening": "Return to Jaipur (96km, 2 hours) or overnight.",
            "recommended_hotel_budget": "Basic guesthouses (Tonk is a day trip from Jaipur)",
            "recommended_hotel_mid": "Return to Jaipur",
            "recommended_hotel_luxury": "Return to Jaipur",
            "must_eat": "Tonk nihari (mutton stew, morning only). Local Nawabi food culture. Biryani at old city restaurants.",
        },
    ],
    "Karauli": [
        {
            "morning": "Karauli City Palace (₹100) — one of Rajasthan's most authentic and uncrowded palaces. Still occupied by the royal family. Extraordinary painted rooms.",
            "afternoon": "Kaila Devi Temple (23km) — important pilgrimage site, ancient stone carvings.",
            "evening": "Return to Sawai Madhopur (55km) or stay overnight in Karauli.",
            "recommended_hotel_budget": "Pratap Palace Heritage (₹1500)",
            "recommended_hotel_mid": "Bhanwar Vilas Palace (₹5000, royal property)",
            "recommended_hotel_luxury": "Bhanwar Vilas Palace",
            "must_eat": "Palace guesthouse meals. Local market thali.",
        },
    ],
}


def normalize_city(name: str):
    name = name.strip()
    for city in CITY_STOPS:
        if city.lower() == name.lower():
            return city
    # Partial match
    for city in CITY_STOPS:
        if city.lower() in name.lower() or name.lower() in city.lower():
            return city
    return None


def plan_itinerary(cities: list, days: int, travelers: int = 2, style: str = "balanced",
                   total_budget=None, budget_scope: str = "per person", interests: str = None):
    """
    Full itinerary plan with real activities, hotel recommendations, restaurant picks,
    entry fees, and practical notes.
    """
    interests_lower = (interests or "").lower()
    cities = [normalize_city(c) for c in cities if normalize_city(c)] or ["Jaipur"]
    days = max(len(cities), int(days))
    itinerary = []

    for day in range(1, days + 1):
        city_index = min(len(cities) - 1, (day - 1) * len(cities) // days)
        city = cities[city_index]
        stops_list = CITY_STOPS[city]
        stop = stops_list[(day - 1) % len(stops_list)]

        # Select hotel rec based on style
        if style == "budget":
            hotel_rec = stop.get("recommended_hotel_budget", "Verified guesthouse near city centre")
        elif style == "premium":
            hotel_rec = stop.get("recommended_hotel_luxury", "Heritage palace hotel")
        else:
            hotel_rec = stop.get("recommended_hotel_mid", "Mid-range heritage hotel")

        transfer = "Local auto-rickshaw or cab (₹50–300 for most city routes)"
        if day > 1:
            prev_city = cities[min(len(cities) - 1, (day - 2) * len(cities) // days)]
            if city != prev_city:
                from tools import get_cab_rates
                route = get_cab_rates(prev_city, city)
                if route.get("options"):
                    best = route["options"][0]
                    transfer = f"Intercity transfer: {prev_city} → {city} ({best['mode']}, {best['duration']}, {best['cost']})"
                else:
                    transfer = f"Intercity transfer: {prev_city} → {city} — verify current schedules and book in advance"

        # Dietary adjustment
        meal = stop.get("must_eat", "Try a local Rajasthani thali; confirm dietary needs directly.")
        if "vegetarian" in interests_lower:
            meal += " (Vegetarian-friendly options highlighted above — confirm Jain prep separately if needed.)"
        if "vegan" in interests_lower:
            meal += " (Inform restaurants of vegan needs — ghee is used widely in Rajasthani cooking.)"

        itinerary.append({
            "day": day,
            "city": city,
            "morning": stop["morning"],
            "afternoon": stop["afternoon"],
            "evening": stop["evening"],
            "transport": transfer,
            "meal": meal,
            "hotel": hotel_rec,
            "note": "Timings and entry fees are local reference guidance; confirm current details with official sources.",
        })

    budget = calculate_budget(days, travelers, style, len(cities), total_budget, budget_scope)
    stay = {
        "budget": "Guesthouses and hostels (Zostel chain highly recommended) near each city's main area. Average ₹400-1200/night.",
        "balanced": "Mid-range heritage hotels (₹2000-5000/night) near main attractions. Compare breakfast inclusion and pickup. Book 5-7 days ahead in season.",
        "premium": "Heritage palace hotels (₹8000-35,000+/night). Book 2-4 weeks ahead for Oct-March season. The Taj, Oberoi, and independent heritage properties all excellent.",
    }.get(style.lower(), "Choose a verified stay near practical transit.")

    return {
        "cities": cities,
        "itinerary": itinerary,
        "budget": budget,
        "stay_guidance": stay,
        "assumptions": [
            "Activities are local knowledge suggestions, not advance bookings.",
            "Entry fees and timings are approximate — verify before visiting.",
            "Safari permits require advance online booking at rajasthanwildlife.in.",
            "Food suggestions use local reference guidance; confirm hours, menus and dietary suitability directly.",
        ]
    }


def validate_itinerary(itinerary: list) -> dict:
    warnings = []
    for d in itinerary:
        text = " ".join([d.get("morning", ""), d.get("afternoon", ""), d.get("evening", ""), d.get("transport", "")])
        if "safari" in text.lower():
            warnings.append(f"Day {d['day']}: Safari permits must be booked in advance at rajasthanwildlife.in — availability is not guaranteed.")
        if "intercity" in d.get("transport", "").lower() and "sunset" in d.get("evening", "").lower():
            warnings.append(f"Day {d['day']}: Keep evening flexible after an intercity transfer — fatigue and delays are common.")
        if "dilwara" in text.lower():
            warnings.append(f"Day {d['day']}: Dilwara Temples open at noon — plan morning activities accordingly.")
    return {"valid": len(warnings) == 0, "warnings": warnings}


def compare_routes(cities: list) -> dict:
    route = " → ".join(cities)
    transfers = max(0, len(cities) - 1)
    pace = "comfortable" if len(cities) <= 2 else ("moderate" if len(cities) <= 4 else "fast-paced")
    intercity_costs = []
    try:
        from tools import get_cab_rates
        for i in range(len(cities) - 1):
            r = get_cab_rates(cities[i], cities[i + 1])
            if r.get("options"):
                intercity_costs.append(f"{cities[i]}→{cities[i+1]}: {r['options'][0]['cost']} by {r['options'][0]['mode']}")
    except Exception:
        pass
    return {
        "route": route,
        "transfers": transfers,
        "pace": pace,
        "intercity_costs": intercity_costs,
        "note": "Transfer count is deterministic; verify live schedules before booking.",
    }
