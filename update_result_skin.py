import json

# 从result.json文件中手动提取的数据（基于之前看到的内容）
new_results = [
    {
        "quizId": 10,
        "title": "Find Your Perfect Study Buddy Personality",
        "results": [
            {
                "mbtiType": "ESTJ",
                "title": "The Study Drill Sergeant",
                "description": "You're the ultimate study organizer! You create strict schedules, set high standards, and make sure your study buddy stays on track. Your ideal study buddy respects your structure and works as hard as you do, turning study sessions into efficient, goal-oriented power hours. You don't mess around when it comes to grades.",
                "traits": ["Disciplined", "Organized", "Goal-Oriented", "Assertive"],
                "studyTip": "Lighten up a little – study breaks and laughter make learning more effective!"
            },
            {
                "mbtiType": "ESFJ",
                "title": "The Study Cheerleader",
                "description": "You're the encouraging heart of study sessions! You bring snacks, celebrate small wins, and keep your study buddy motivated when they're struggling. Your ideal study buddy appreciates your support and cheers you on in return, making even the hardest subjects feel manageable. You make studying feel like a team effort.",
                "traits": ["Encouraging", "Caring", "Positive", "Reliable"],
                "studyTip": "Don't forget to focus on your own work – you can't cheer others on if you're falling behind!"
            },
            {
                "mbtiType": "ESTP",
                "title": "The Spontaneous Study Buddy",
                "description": "You're the hands-on learner who hates boring study routines! You turn flashcards into games, learn by doing, and switch subjects when you get bored. Your ideal study buddy is as flexible as you are, ready to adapt to new study methods and turn learning into an adventure. You make studying feel less like work and more like fun.",
                "traits": ["Spontaneous", "Practical", "Energetic", "Adaptable"],
                "studyTip": "Set some basic structure – even fun study sessions need focus!"
            },
            {
                "mbtiType": "ESFP",
                "title": "The Social Study Butterfly",
                "description": "You're the study buddy who makes group sessions fun! You love studying with friends, turning discussions into lively conversations, and making new connections over shared notes. Your ideal study buddy is social and positive, and loves learning together in a relaxed, friendly environment. You make studying feel like hanging out with friends.",
                "traits": ["Social", "Playful", "Positive", "Present"],
                "studyTip": "Know when to focus – too much chatting can derail your goals!"
            },
            {
                "mbtiType": "ENTJ",
                "title": "The Study Strategist",
                "description": "You're the big-picture study planner! You analyze test formats, create long-term study plans, and find the most efficient ways to learn. Your ideal study buddy is intelligent and ambitious, able to keep up with your strategic approach and contribute their own ideas. You turn studying into a well-executed mission.",
                "traits": ["Strategic", "Ambitious", "Analytical", "Confident"],
                "studyTip": "Listen to others' study methods – sometimes the simple approach works best!"
            },
            {
                "mbtiType": "ENFJ",
                "title": "The Study Mentor",
                "description": "You're the inspiring study leader! You help your study buddy understand difficult concepts, share your knowledge generously, and motivate them to reach their full potential. Your ideal study buddy is eager to learn and grow, and values your patience and insight. You make learning feel meaningful and empowering.",
                "traits": ["Inspiring", "Patient", "Generous", "Insightful"],
                "studyTip": "Don't take on too much – focus on your own learning goals too!"
            },
            {
                "mbtiType": "ENTP",
                "title": "The Debate Study Buddy",
                "description": "You're the curious study buddy who loves to debate ideas! You ask challenging questions, explore different perspectives, and turn study sessions into intellectual conversations. Your ideal study buddy is sharp and curious, able to keep up with your quick wit and challenge your ideas. You make learning feel dynamic and engaging.",
                "traits": ["Curious", "Witty", "Analytical", "Creative"],
                "studyTip": "Stay on topic – interesting debates can take you off course!"
            },
            {
                "mbtiType": "ENFP",
                "title": "The Creative Study Buddy",
                "description": "You're the imaginative learner who makes studying fun! You create colorful notes, turn memorization into stories, and find creative ways to understand boring subjects. Your ideal study buddy shares your enthusiasm and creativity, and loves exploring new ways to learn with you. You make even the driest material feel interesting.",
                "traits": ["Creative", "Enthusiastic", "Imaginative", "Optimistic"],
                "studyTip": "Balance creativity with focus – pretty notes don't mean you're learning!"
            },
            {
                "mbtiType": "ISTJ",
                "title": "The Reliable Study Buddy",
                "description": "You're the steady, dependable study companion! You show up on time, take detailed notes, and stick to the study plan no matter what. Your ideal study buddy appreciates your reliability and matches your work ethic, making study sessions consistent and productive. You're the rock of every study group.",
                "traits": ["Reliable", "Detail-Oriented", "Consistent", "Practical"],
                "studyTip": "Be open to new study methods – routine is good, but flexibility is too!"
            },
            {
                "mbtiType": "ISFJ",
                "title": "The Thoughtful Study Buddy",
                "description": "You're the caring study companion who remembers everything! You bring extra pens, share your notes with absent friends, and check in on your study buddy's mental health. Your ideal study buddy values your kindness and reciprocates your care, making study sessions feel supportive and safe. You prioritize people over perfect grades.",
                "traits": ["Thoughtful", "Caring", "Observant", "Loyal"],
                "studyTip": "Set boundaries – you can't take care of everyone all the time!"
            },
            {
                "mbtiType": "ISTP",
                "title": "The Hands-On Study Buddy",
                "description": "You're the practical learner who hates rote memorization! You learn by doing, solve problems step-by-step, and stay calm under pressure. Your ideal study buddy respects your independent approach and doesn't push you to study in ways that don't work for you. You're the quiet problem-solver of every study group.",
                "traits": ["Practical", "Calm", "Independent", "Resourceful"],
                "studyTip": "Try explaining your ideas out loud – teaching others reinforces learning!"
            },
            {
                "mbtiType": "ISFP",
                "title": "The Intuitive Study Buddy",
                "description": "You're the sensitive learner who connects with material on a deep level! You remember concepts through feelings and experiences, and find beauty in even the most technical subjects. Your ideal study buddy is gentle and understanding, and appreciates your unique way of learning. You make studying feel personal and meaningful.",
                "traits": ["Intuitive", "Sensitive", "Creative", "Present"],
                "studyTip": "Use structure to support your intuition – organization helps your ideas shine!"
            },
            {
                "mbtiType": "INTJ",
                "title": "The Independent Study Genius",
                "description": "You're the self-directed learner who needs minimal supervision! You create your own study plans, dive deep into complex topics, and work best alone. Your ideal study buddy respects your need for space and intellectual independence, and only joins you for high-level discussions. You're the master of self-learning.",
                "traits": ["Independent", "Analytical", "Strategic", "Focused"],
                "studyTip": "Collaborate occasionally – others can bring new insights to your work!"
            },
            {
                "mbtiType": "INFJ",
                "title": "The Insightful Study Buddy",
                "description": "You're the deep thinker who sees connections others miss! You understand the underlying meaning of material, ask profound questions, and study with purpose. Your ideal study buddy values your insight and engages in meaningful conversations with you, making studying feel like a journey of discovery. You make learning feel transformative.",
                "traits": ["Insightful", "Purposeful", "Intuitive", "Reflective"],
                "studyTip": "Don't overthink – sometimes the simplest answer is the right one!"
            },
            {
                "mbtiType": "INTP",
                "title": "The Curious Study Nerd",
                "description": "You're the analytical learner who loves to dig deep! You ask endless questions, explore tangents, and understand concepts from every angle. Your ideal study buddy shares your curiosity and intellectual rigor, and doesn't mind when you go off on interesting tangents. You're the brain of every study group.",
                "traits": ["Curious", "Analytical", "Intellectual", "Creative"],
                "studyTip": "Stay focused on the goal – tangents are fun, but deadlines matter!"
            },
            {
                "mbtiType": "INFP",
                "title": "The Idealistic Study Buddy",
                "description": "You're the dreamy learner who studies for passion, not grades! You connect material to your values and dreams, and find meaning in even the most mundane subjects. Your ideal study buddy shares your idealism and helps you stay motivated when learning feels pointless. You make studying feel like a journey of self-discovery.",
                "traits": ["Idealistic", "Passionate", "Empathetic", "Creative"],
                "studyTip": "Balance passion with practicality – grades matter too!"
            }
        ]
    },
    {
        "quizId": 11,
        "title": "What's Your Ideal Workout Buddy Personality?",
        "results": [
            {
                "mbtiType": "ESTJ",
                "title": "The Fitness Drill Sergeant",
                "description": "You're the no-nonsense workout leader! You create strict fitness plans, track every rep, and push your workout buddy to meet their goals. Your ideal workout buddy respects your discipline and matches your work ethic, turning every gym session into a focused, results-driven challenge. You don't skip reps – ever.",
                "traits": ["Disciplined", "Goal-Oriented", "Assertive", "Reliable"],
                "fitnessTip": "Add fun to your workouts – progress doesn't have to be miserable!"
            },
            {
                "mbtiType": "ESFJ",
                "title": "The Fitness Cheerleader",
                "description": "You're the encouraging workout buddy who makes every rep feel achievable! You celebrate small wins, bring positive energy, and lift your buddy up when they're struggling. Your ideal workout buddy appreciates your support and cheers you on in return, making even the hardest workouts feel like a team effort.",
                "traits": ["Encouraging", "Positive", "Caring", "Energetic"],
                "fitnessTip": "Focus on your own form – don't neglect your body to cheer others on!"
            },
            {
                "mbtiType": "ESTP",
                "title": "The Fitness Daredevil",
                "description": "You're the spontaneous workout buddy who loves to push limits! You try new exercises, turn workouts into competitions, and hate boring routines. Your ideal workout buddy is as bold as you are, ready to try risky moves and turn every gym session into an adventure. You make fitness feel like play.",
                "traits": ["Bold", "Spontaneous", "Competitive", "Fearless"],
                "fitnessTip": "Prioritize safety – pushing limits is good, but injury is not!"
            },
            {
                "mbtiType": "ESFP",
                "title": "The Fitness Social Butterfly",
                "description": "You're the fun-loving workout buddy who makes group classes a party! You make friends at the gym, laugh through tough workouts, and turn fitness into a social event. Your ideal workout buddy is outgoing and positive, and loves sweating together in a lively, supportive environment. You make exercise feel like hanging out.",
                "traits": ["Social", "Playful", "Positive", "Present"],
                "fitnessTip": "Focus on your workout – too much chatting can reduce intensity!"
            },
            {
                "mbtiType": "ENTJ",
                "title": "The Fitness Strategist",
                "description": "You're the big-picture fitness planner! You analyze workout science, create long-term training programs, and find the most efficient ways to build strength. Your ideal workout buddy is ambitious and intelligent, able to keep up with your strategic approach and contribute their own fitness ideas. You turn working out into a well-executed plan.",
                "traits": ["Strategic", "Ambitious", "Analytical", "Confident"],
                "fitnessTip": "Listen to your body – even the best plan needs to adapt to how you feel!"
            },
            {
                "mbtiType": "ENFJ",
                "title": "The Fitness Mentor",
                "description": "You're the inspiring fitness leader who helps others grow! You teach proper form, share your fitness knowledge, and motivate your buddy to become their strongest self. Your ideal workout buddy is eager to learn and grow, and values your patience and guidance. You make fitness feel empowering and transformative.",
                "traits": ["Inspiring", "Patient", "Generous", "Insightful"],
                "fitnessTip": "Don't take on too much – focus on your own fitness journey too!"
            },
            {
                "mbtiType": "ENTP",
                "title": "The Fitness Innovator",
                "description": "You're the curious workout buddy who loves to experiment! You try new fitness trends, debate workout science, and find creative ways to make exercise effective. Your ideal workout buddy is sharp and curious, able to keep up with your quick wit and challenge your fitness ideas. You make working out feel dynamic and interesting.",
                "traits": ["Curious", "Creative", "Witty", "Adaptable"],
                "fitnessTip": "Stick with a routine long enough to see results – constant change slows progress!"
            },
            {
                "mbtiType": "ENFP",
                "title": "The Fitness Dreamer",
                "description": "You're the optimistic workout buddy who makes fitness feel magical! You set big fitness goals, find joy in movement, and see exercise as a way to grow. Your ideal workout buddy shares your enthusiasm and optimism, and joins you in chasing your fitness dreams. You make even the hardest workouts feel hopeful.",
                "traits": ["Optimistic", "Enthusiastic", "Imaginative", "Passionate"],
                "fitnessTip": "Set realistic short-term goals – big dreams need small steps!"
            },
            {
                "mbtiType": "ISTJ",
                "title": "The Reliable Fitness Buddy",
                "description": "You're the steady, consistent workout companion! You show up on time, follow your routine exactly, and track every workout detail. Your ideal workout buddy appreciates your reliability and matches your consistency, making fitness a predictable, sustainable part of life. You're the rock of every workout partnership.",
                "traits": ["Reliable", "Consistent", "Detail-Oriented", "Practical"],
                "fitnessTip": "Be open to small changes – routine is good, but adaptability prevents boredom!"
            },
            {
                "mbtiType": "ISFJ",
                "title": "The Caring Fitness Buddy",
                "description": "You're the thoughtful workout companion who looks out for others! You bring water and towels, check on form to prevent injury, and remember your buddy's fitness limits. Your ideal workout buddy values your care and reciprocates your kindness, making every gym session feel safe and supportive. You prioritize health over intensity.",
                "traits": ["Caring", "Observant", "Gentle", "Loyal"],
                "fitnessTip": "Advocate for yourself – don't neglect your own needs to care for others!"
            },
            {
                "mbtiType": "ISTP",
                "title": "The Hands-On Fitness Buddy",
                "description": "You're the practical workout buddy who learns by doing! You master new exercises quickly, fix form issues with your hands, and stay calm during tough workouts. Your ideal workout buddy respects your independent approach and doesn't push you to talk or socialize during exercise. You're the quiet expert of the gym.",
                "traits": ["Practical", "Calm", "Independent", "Skilled"],
                "fitnessTip": "Share your knowledge – teaching others reinforces your own skills!"
            },
            {
                "mbtiType": "ISFP",
                "title": "The Intuitive Fitness Buddy",
                "description": "You're the sensitive workout buddy who connects with movement! You feel your body's limits, find joy in physical expression, and value fitness for how it makes you feel. Your ideal workout buddy is gentle and understanding, and appreciates your unique approach to exercise. You make fitness feel personal and meaningful.",
                "traits": ["Intuitive", "Sensitive", "Creative", "Present"],
                "fitnessTip": "Set small goals – tracking progress helps you stay motivated!"
            },
            {
                "mbtiType": "INTJ",
                "title": "The Independent Fitness Genius",
                "description": "You're the self-directed workout buddy who needs minimal guidance! You research fitness science, create your own programs, and work best alone. Your ideal workout buddy respects your need for space and intellectual independence, and only joins you for high-level fitness discussions. You're the master of self-training.",
                "traits": ["Independent", "Analytical", "Strategic", "Focused"],
                "fitnessTip": "Work out with others occasionally – accountability boosts consistency!"
            },
            {
                "mbtiType": "INFJ",
                "title": "The Insightful Fitness Buddy",
                "description": "You're the deep-thinking workout buddy who sees fitness as self-care! You understand the mind-body connection, use exercise to relieve stress, and work out with purpose. Your ideal workout buddy values your insight and engages in meaningful conversations about health, making fitness feel like a journey of self-discovery.",
                "traits": ["Insightful", "Purposeful", "Intuitive", "Compassionate"],
                "fitnessTip": "Don't overanalyze – sometimes just moving your body is enough!"
            },
            {
                "mbtiType": "INTP",
                "title": "The Fitness Nerd",
                "description": "You're the curious workout buddy who loves to analyze fitness! You research exercise physiology, debate training methods, and understand the science behind every rep. Your ideal workout buddy shares your curiosity and intellectual rigor, and doesn't mind when you go off on fitness tangents. You're the brain of every gym group.",
                "traits": ["Curious", "Analytical", "Intellectual", "Creative"],
                "fitnessTip": "Stop overthinking and start moving – action beats theory!"
            },
            {
                "mbtiType": "INFP",
                "title": "The Idealistic Fitness Buddy",
                "description": "You're the dreamy workout buddy who exercises for joy, not perfection! You connect fitness to your values, find meaning in movement, and prioritize mental health over physical appearance. Your ideal workout buddy shares your idealism and helps you stay motivated when exercise feels hard. You make fitness feel like self-love.",
                "traits": ["Idealistic", "Compassionate", "Creative", "Passionate"],
                "fitnessTip": "Create a sustainable routine – consistency beats intensity for long-term joy!"
            }
        ]
    },
    {
        "quizId": 12,
        "title": "What's Your Ideal Work Colleague Personality?",
        "results": [
            {
                "mbtiType": "ESTJ",
                "title": "The Office Leader",
                "description": "You're the reliable, structured colleague who keeps the team on track! You create clear processes, meet deadlines without fail, and hold everyone accountable. Your ideal work buddy respects your authority and matches your strong work ethic, making projects run smoothly and efficiently. You're the backbone of every successful team.",
                "traits": ["Organized", "Responsible", "Decisive", "Reliable"],
                "workTip": "Learn to delegate – you don't have to control every detail to succeed!"
            },
            {
                "mbtiType": "ESFJ",
                "title": "The Office Caregiver",
                "description": "You're the warm, supportive colleague who makes the workplace feel like home! You remember birthdays, check in on stressed teammates, and foster a positive work environment. Your ideal work buddy appreciates your kindness and reciprocates your care, making even busy workdays feel enjoyable and connected.",
                "traits": ["Caring", "Social", "Nurturing", "Cooperative"],
                "workTip": "Set boundaries – you can't take care of everyone without burning out!"
            },
            {
                "mbtiType": "ESTP",
                "title": "The Office Problem-Solver",
                "description": "You're the quick-thinking, hands-on colleague who thrives under pressure! You solve unexpected problems, adapt to changing priorities, and turn crises into opportunities. Your ideal work buddy is as flexible as you are, ready to jump into action and tackle challenges head-on. You make the workplace feel dynamic and exciting.",
                "traits": ["Adaptable", "Practical", "Bold", "Energetic"],
                "workTip": "Plan ahead occasionally – quick fixes don't solve long-term issues!"
            },
            {
                "mbtiType": "ESFP",
                "title": "The Office Social Butterfly",
                "description": "You're the cheerful, outgoing colleague who boosts team morale! You organize office events, make meetings fun, and build connections between teammates. Your ideal work buddy is social and positive, and loves collaborating in a lively, supportive environment. You make work feel less like a chore and more like a community.",
                "traits": ["Social", "Playful", "Positive", "Present"],
                "workTip": "Balance fun with focus – too much socializing can derail productivity!"
            },
            {
                "mbtiType": "ENTJ",
                "title": "The Office Visionary",
                "description": "You're the strategic, ambitious colleague who leads the team to success! You set big goals, create long-term plans, and inspire others to reach their potential. Your ideal work buddy is intelligent and driven, able to keep up with your big-picture thinking and contribute meaningful ideas. You turn ordinary projects into extraordinary successes.",
                "traits": ["Strategic", "Ambitious", "Confident", "Visionary"],
                "workTip": "Listen to your team – great ideas can come from anywhere, not just the top!"
            },
            {
                "mbtiType": "ENFJ",
                "title": "The Office Mentor",
                "description": "You're the inspiring, empathetic colleague who helps others grow! You mentor new teammates, share your knowledge generously, and advocate for your team's needs. Your ideal work buddy is eager to learn and grow, and values your guidance and support. You make the workplace feel like a place for growth and development.",
                "traits": ["Inspiring", "Empathetic", "Wise", "Generous"],
                "workTip": "Focus on your own goals – you can't mentor everyone and still advance your career!"
            },
            {
                "mbtiType": "ENTP",
                "title": "The Office Innovator",
                "description": "You're the creative, curious colleague who challenges the status quo! You brainstorm new ideas, debate processes, and find innovative solutions to old problems. Your ideal work buddy is sharp and open-minded, able to keep up with your quick wit and challenge your ideas. You make the workplace feel dynamic and forward-thinking.",
                "traits": ["Creative", "Curious", "Witty", "Adaptable"],
                "workTip": "Follow through on your ideas – great concepts need execution to succeed!"
            },
            {
                "mbtiType": "ENFP",
                "title": "The Office Dreamer",
                "description": "You're the optimistic, imaginative colleague who brings joy to work! You see possibilities where others see obstacles, inspire creativity in your team, and make even boring tasks feel meaningful. Your ideal work buddy shares your optimism and creativity, and joins you in chasing big, bold ideas. You're the heart of every innovative team.",
                "traits": ["Optimistic", "Imaginative", "Enthusiastic", "Creative"],
                "workTip": "Ground your ideas in reality – dreams need practical steps to become real!"
            },
            {
                "mbtiType": "ISTJ",
                "title": "The Office Reliable",
                "description": "You're the steady, detail-oriented colleague who gets things done! You follow processes to the letter, catch mistakes others miss, and deliver high-quality work on time. Your ideal work buddy appreciates your reliability and matches your attention to detail, making projects consistent and error-free. You're the rock every team needs.",
                "traits": ["Reliable", "Detail-Oriented", "Consistent", "Practical"],
                "workTip": "Be open to new methods – tradition is good, but innovation drives growth!"
            },
            {
                "mbtiType": "ISFJ",
                "title": "The Office Supporter",
                "description": "You're the quiet, thoughtful colleague who makes the team run smoothly! You anticipate needs, handle administrative tasks without being asked, and support your teammates behind the scenes. Your ideal work buddy values your quiet contributions and acknowledges your hard work, making you feel seen and appreciated.",
                "traits": ["Thoughtful", "Loyal", "Observant", "Cooperative"],
                "workTip": "Speak up for yourself – your needs and ideas matter just as much as others'!"
            },
            {
                "mbtiType": "ISTP",
                "title": "The Office Technician",
                "description": "You're the calm, practical colleague who fixes problems no one else can! You troubleshoot technical issues, streamline processes, and work independently without supervision. Your ideal work buddy respects your need for autonomy and doesn't micromanage your work. You're the quiet expert every office relies on.",
                "traits": ["Practical", "Calm", "Independent", "Resourceful"],
                "workTip": "Communicate your progress – even independent workers need to update the team!"
            },
            {
                "mbtiType": "ISFP",
                "title": "The Office Artist",
                "description": "You're the creative, sensitive colleague who brings beauty to work! You design visually appealing projects, connect with clients on an emotional level, and value authenticity in your work. Your ideal work buddy is gentle and understanding, and appreciates your unique creative perspective. You make work feel personal and meaningful.",
                "traits": ["Creative", "Sensitive", "Authentic", "Present"],
                "workTip": "Advocate for your ideas – your creative vision is valuable to the team!"
            },
            {
                "mbtiType": "INTJ",
                "title": "The Office Strategist",
                "description": "You're the independent, analytical colleague who plans for success! You research market trends, anticipate challenges, and create foolproof strategies for projects. Your ideal work buddy respects your need for space and intellectual independence, and only engages in high-level strategic discussions. You're the mastermind behind every successful initiative.",
                "traits": ["Analytical", "Independent", "Strategic", "Focused"],
                "workTip": "Collaborate with the team – your strategy needs buy-in to succeed!"
            },
            {
                "mbtiType": "INFJ",
                "title": "The Office Empath",
                "description": "You're the insightful, compassionate colleague who understands people! You read team dynamics, anticipate client needs, and bring emotional intelligence to every interaction. Your ideal work buddy values your deep understanding of others and appreciates your thoughtful approach to work. You make the workplace feel more human and connected.",
                "traits": ["Insightful", "Compassionate", "Intuitive", "Purposeful"],
                "workTip": "Protect your energy – absorbing others' emotions can lead to burnout!"
            },
            {
                "mbtiType": "INTP",
                "title": "The Office Thinker",
                "description": "You're the curious, analytical colleague who solves complex problems! You dive deep into data, question assumptions, and find logical solutions to challenging issues. Your ideal work buddy shares your love of learning and enjoys intellectual discussions, even if you get lost in your thoughts for hours. You're the brain of every problem-solving team.",
                "traits": ["Curious", "Analytical", "Intellectual", "Creative"],
                "workTip": "Communicate your ideas clearly – complex thoughts need simple explanations!"
            },
            {
                "mbtiType": "INFP",
                "title": "The Office Idealist",
                "description": "You're the gentle, purpose-driven colleague who works with passion! You connect your work to your values, advocate for what's right, and bring heart to every project. Your ideal work buddy shares your idealism and helps you stay true to your values in a corporate world. You make work feel meaningful and purposeful.",
                "traits": ["Idealistic", "Compassionate", "Creative", "Purposeful"],
                "workTip": "Be practical about your ideals – small, consistent actions create real change!"
            }
        ]
    },
    {
        "quizId": 13,
        "title": "What's Your Ideal Pet Parent Personality?",
        "results": [
            {
                "mbtiType": "ESTJ",
                "title": "The Pet Parent Drill Sergeant",
                "description": "You're the structured, disciplined pet parent who sets clear rules and routines! You create a consistent schedule for your pet, train them with firm kindness, and make sure they follow household rules. Your ideal pet appreciates your consistency and thrives under your reliable leadership. You're the pet parent who ensures your furry friend is well-behaved and cared for.",
                "traits": ["Disciplined", "Structured", "Reliable", "Firm"],
                "petTip": "Let loose occasionally – pets need fun and playtime too!"
            },
            {
                "mbtiType": "ESFJ",
                "title": "The Nurturing Pet Parent",
                "description": "You're the warm, caring pet parent who puts your pet's needs first! You spoil your pet with love and attention, remember their favorite treats, and make sure they feel safe and secure. Your ideal pet is affectionate and appreciates your constant care and attention. You're the pet parent who turns your home into a pet paradise.",
                "traits": ["Caring", "Nurturing", "Attentive", "Loving"],
                "petTip": "Set boundaries – even pets need rules to feel secure!"
            },
            {
                "mbtiType": "ESTP",
                "title": "The Adventure Pet Parent",
                "description": "You're the active, spontaneous pet parent who loves outdoor adventures! You take your pet on hikes, to the beach, and on road trips, turning every day into an exciting adventure. Your ideal pet is energetic and loves exploring the world with you. You're the pet parent who creates unforgettable memories with your furry companion.",
                "traits": ["Adventurous", "Spontaneous", "Energetic", "Active"],
                "petTip": "Make time for rest – even adventure pets need downtime!"
            },
            {
                "mbtiType": "ESFP",
                "title": "The Social Pet Parent",
                "description": "You're the outgoing, friendly pet parent who loves showing off your pet! You take your pet to parks, pet cafes, and social events, making them the center of attention. Your ideal pet is sociable and loves meeting new people and animals. You're the pet parent who turns your pet into a local celebrity.",
                "traits": ["Social", "Friendly", "Outgoing", "Playful"],
                "petTip": "Respect your pet's boundaries – not all pets love constant socializing!"
            },
            {
                "mbtiType": "ENTJ",
                "title": "The Strategic Pet Parent",
                "description": "You're the goal-oriented, strategic pet parent who plans for your pet's future! You research the best food, training methods, and healthcare options, creating a long-term plan for your pet's well-being. Your ideal pet is intelligent and responds well to your structured approach. You're the pet parent who ensures your pet has the best possible life.",
                "traits": ["Strategic", "Goal-Oriented", "Research-Driven", "Planned"],
                "petTip": "Be flexible – pets have their own personalities and needs!"
            },
            {
                "mbtiType": "ENFJ",
                "title": "The Inspirational Pet Parent",
                "description": "You're the empathetic, inspiring pet parent who connects deeply with your pet! You understand your pet's emotions, advocate for animal welfare, and use your bond to inspire others. Your ideal pet is sensitive and responds well to your emotional support. You're the pet parent who creates a deep, meaningful bond with your furry friend.",
                "traits": ["Empathetic", "Inspiring", "Advocative", "Bonded"],
                "petTip": "Take care of yourself – you can't support your pet if you're burnt out!"
            },
            {
                "mbtiType": "ENTP",
                "title": "The Innovative Pet Parent",
                "description": "You're the creative, curious pet parent who loves experimenting! You try new training methods, create DIY toys, and find innovative solutions to pet care challenges. Your ideal pet is adaptable and enjoys your creative approach. You're the pet parent who turns ordinary pet care into an exciting experiment.",
                "traits": ["Creative", "Innovative", "Curious", "Experimental"],
                "petTip": "Stick with what works – not every experiment needs to be permanent!"
            },
            {
                "mbtiType": "ENFP",
                "title": "The Dreamy Pet Parent",
                "description": "You're the optimistic, imaginative pet parent who sees the best in your pet! You create elaborate stories about your pet's adventures, spoil them with love, and believe they're capable of anything. Your ideal pet is playful and responds well to your positive energy. You're the pet parent who makes every day magical for your furry friend.",
                "traits": ["Optimistic", "Imaginative", "Playful", "Loving"],
                "petTip": "Be realistic – pets have limitations too!"
            },
            {
                "mbtiType": "ISTJ",
                "title": "The Reliable Pet Parent",
                "description": "You're the steady, dependable pet parent who follows through on commitments! You never miss a vet appointment, always keep your pet's supplies stocked, and provide consistent care. Your ideal pet appreciates your reliability and thrives in a stable environment. You're the pet parent who ensures your pet's needs are always met.",
                "traits": ["Reliable", "Consistent", "Dependable", "Organized"],
                "petTip": "Be open to spontaneity – pets enjoy surprises too!"
            },
            {
                "mbtiType": "ISFJ",
                "title": "The Caring Pet Parent",
                "description": "You're the thoughtful, observant pet parent who notices every detail! You remember your pet's preferences, anticipate their needs, and provide gentle care. Your ideal pet is sensitive and appreciates your quiet devotion. You're the pet parent who creates a safe, loving home for your furry friend.",
                "traits": ["Thoughtful", "Observant", "Gentle", "Caring"],
                "petTip": "Share your care with others – your pet can benefit from socialization!"
            },
            {
                "mbtiType": "ISTP",
                "title": "The Hands-On Pet Parent",
                "description": "You're the practical, hands-on pet parent who fixes problems yourself! You groom your pet at home, build them custom toys, and handle minor health issues with confidence. Your ideal pet is independent and appreciates your practical approach. You're the pet parent who takes care of business when it comes to pet care.",
                "traits": ["Practical", "Hands-On", "Independent", "Resourceful"],
                "petTip": "Ask for help when needed – some pet issues require professionals!"
            },
            {
                "mbtiType": "ISFP",
                "title": "The Artistic Pet Parent",
                "description": "You're the creative, sensitive pet parent who connects with your pet on a deep level! You take beautiful photos of your pet, create art inspired by them, and appreciate their unique personality. Your ideal pet is gentle and responds well to your artistic energy. You're the pet parent who sees your pet as a muse and a friend.",
                "traits": ["Creative", "Sensitive", "Artistic", "Observant"],
                "petTip": "Balance art with practicality – pets need basic care too!"
            },
            {
                "mbtiType": "INTJ",
                "title": "The Analytical Pet Parent",
                "description": "You're the strategic, analytical pet parent who plans for every scenario! You research pet behavior, create detailed care plans, and make decisions based on data. Your ideal pet is intelligent and responds well to your logical approach. You're the pet parent who ensures your pet's care is based on science and strategy.",
                "traits": ["Analytical", "Strategic", "Research-Driven", "Logical"],
                "petTip": "Trust your intuition – pets aren't just data points!"
            },
            {
                "mbtiType": "INFJ",
                "title": "The Insightful Pet Parent",
                "description": "You're the intuitive, insightful pet parent who understands your pet's soul! You sense when your pet is upset, anticipate their needs, and create a deep emotional bond. Your ideal pet is sensitive and responds well to your intuitive care. You're the pet parent who truly understands what makes your furry friend tick.",
                "traits": ["Intuitive", "Insightful", "Empathetic", "Bonded"],
                "petTip": "Don't overanalyze – sometimes pets just need simple care!"
            },
            {
                "mbtiType": "INTP",
                "title": "The Curious Pet Parent",
                "description": "You're the inquisitive, analytical pet parent who loves learning about pets! You study animal behavior, experiment with different training methods, and enjoy solving pet-related puzzles. Your ideal pet is intelligent and enjoys your mental stimulation. You're the pet parent who turns pet care into a fascinating learning experience.",
                "traits": ["Curious", "Analytical", "Inquisitive", "Intellectual"],
                "petTip": "Remember to play – pets need fun, not just mental stimulation!"
            },
            {
                "mbtiType": "INFP",
                "title": "The Idealistic Pet Parent",
                "description": "You're the compassionate, idealistic pet parent who sees your pet as a family member! You advocate for animal rights, create a loving home environment, and believe in the power of unconditional love. Your ideal pet is gentle and responds well to your kind-hearted approach. You're the pet parent who treats your furry friend with the respect and love they deserve.",
                "traits": ["Compassionate", "Idealistic", "Loving", "Advocative"],
                "petTip": "Be practical – pets have basic needs that can't be ignored!"
            }
        ]
    }
]

# 读取现有的result_skin.json文件
with open('/Users/jerrysrick/.openclaw/workspace/psych-test/data/result_skin.json', 'r', encoding='utf-8') as f:
    skin_data = json.load(f)

# 为新测试创建test_id映射
test_id_mapping = {
    "Find Your Perfect Study Buddy Personality": "study_buddy",
    "What's Your Ideal Workout Buddy Personality?": "workout_buddy",
    "What's Your Ideal Work Colleague Personality?": "work_colleague",
    "What's Your Ideal Pet Parent Personality?": "pet_parent"
}

# 添加新测试数据
for result in new_results:
    title = result["title"]
    if title in test_id_mapping:
        test_id = test_id_mapping[title]
        # 创建新的测试对象
        new_test = {
            "test_id": test_id,
            "title": title,
            "results": result["results"]
        }
        # 检查是否已存在
        if not any(test["title"] == title for test in skin_data):
            skin_data.append(new_test)
            print(f'✓ 添加测试: {title} (test_id: {test_id})')
        else:
            print(f'✗ 测试已存在: {title}')

# 保存更新后的数据
with open('/Users/jerrysrick/.openclaw/workspace/psych-test/data/result_skin.json', 'w', encoding='utf-8') as f:
    json.dump(skin_data, f, indent=2, ensure_ascii=False)

print(f'\n✓ 成功更新result_skin.json文件')
print(f'✓ 总测试数量: {len(skin_data)}')

# 分析数据匹配情况
print('\n' + '='*50)
print('数据匹配分析:')
print('='*50)

# 读取test_data.json
with open('/Users/jerrysrick/.openclaw/workspace/psych-test/data/test_data.json', 'r', encoding='utf-8') as f:
    test_data = json.load(f)

# 提取标题
skin_titles = [test["title"] for test in skin_data]
test_titles = [test["title"] for test in test_data]

print('\nTest_data.json 与 Result_skin.json 匹配情况:')
for title in test_titles:
    if title in skin_titles:
        print(f'✓ 匹配: {title}')
    else:
        print(f'✗ 不匹配: {title}')

print('\nResult_skin.json 中的测试:')
for i, test in enumerate(skin_data):
    print(f'{i+1}. test_id: {test["test_id"]}, title: {test["title"]}')
