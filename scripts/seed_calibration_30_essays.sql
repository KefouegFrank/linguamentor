-- =================================================================
-- Calibration seed — 30 IELTS Academic essays
-- =================================================================
-- Coverage: bands 4.5 through 8.5 (6 essays per band tier)
-- Tier 1: Band 4.5-5.0  (bbbbbbbb series) — below threshold writers
-- Tier 2: Band 5.5-6.5  (aaaaaaaa series) — original 5 essays retained
-- Tier 3: Band 7.0      (cccccccc series) — competent writers
-- Tier 4: Band 7.5-8.0  (dddddddd series) — proficient writers
-- Tier 5: Band 8.5      (eeeeeeee series) — near-expert writers
--
-- Each essay has 2 human graders with realistic inter-rater variance.
-- Human scores follow IELTS convention: ±0.5 band disagreement is
-- normal and acceptable; anything beyond triggers adjudication.
--
-- Run with:
--   docker cp scripts/seed_calibration_30_essays.sql lm_postgres:/tmp/seed30.sql
--   docker exec lm_postgres psql -U lm_user -d linguamentor -f /tmp/seed30.sql
-- =================================================================

SET search_path TO linguamentor, public;

-- Clear previous test data cleanly
DELETE FROM linguamentor.calibration_ai_scores;
DELETE FROM linguamentor.calibration_runs;
DELETE FROM linguamentor.calibration_human_scores
WHERE essay_id IN (
    SELECT id FROM linguamentor.calibration_essays WHERE source = 'test-seed'
);
DELETE FROM linguamentor.calibration_essays WHERE source = 'test-seed';

-- =================================================================
-- TIER 1: Band 4.5-5.0 — Below threshold writers
-- Characteristics: limited vocabulary, frequent grammar errors,
-- ideas present but underdeveloped, weak cohesion
-- =================================================================

INSERT INTO linguamentor.calibration_essays
    (id, exam_type, task_prompt, essay_text, approximate_band, source, word_count, grading_complete)
VALUES
(
    'bbbbbbbb-0001-0001-0001-bbbbbbbbbbbb',
    'ielts_academic',
    'Some people believe that universities should focus only on academic subjects. Others think they should also prepare students for employment. Discuss both views and give your own opinion.',
    'Nowadays many people have different opinion about university. Some think university only for study academic things. Other people say university must help students get job. I think both have good points.

People who think only academic is good because student can learn many knowledge. When student study hard they become clever person. University is place for learn not for work training. This is main reason why academic is important.

But other people think university must prepare student for job. Because after university student need find job. If they not have skill they cannot find job easy. Many company want person with skill not only certificate.

In my opinion university should do both. Student need academic knowledge and also need job skill. If university only do one thing student will have problem. So university must balance academic and job preparation. This will help student in future.

In conclusion both view have merit. University must consider both academic and employment needs of students.',
    4.5,
    'test-seed',
    178,
    TRUE
),
(
    'bbbbbbbb-0002-0002-0002-bbbbbbbbbbbb',
    'ielts_academic',
    'The increasing use of technology in education has both advantages and disadvantages. Discuss.',
    'Technology in education is very common now. It has good things and bad things. I will discuss both in this essay.

First advantage is student can learn easy with technology. Computer and internet help student find information fast. Before internet student must go library but now they can use google. This save time and is convenient for student.

Second advantage is technology make lesson more interesting. Teacher can use video and picture to explain. Student understand more when they see picture not only read book. So technology help student learn better.

But technology also have disadvantage. Student become lazy because they copy from internet. They not think by themselves when they have internet. This is big problem for education.

Another problem is not all student have computer at home. Poor student cannot afford technology. So technology create inequality in education system. Rich student have advantage over poor student.

To sum up technology in education have both advantage and disadvantage. Government should make sure all student can access technology equally.',
    4.5,
    'test-seed',
    172,
    TRUE
),
(
    'bbbbbbbb-0003-0003-0003-bbbbbbbbbbbb',
    'ielts_academic',
    'In many countries, the proportion of older people is increasing. What are the causes of this trend and what are the effects on society?',
    'In many country old people number is growing. There are some reason for this and it effect society in different way.

The main cause of more old people is medicine improve. Doctor can treat many disease now that before was not possible. So people not die young and they live long time. Also food is better now and people eat healthy so they live longer.

Another cause is birth rate go down. Young people today have less children than before. In old days family have many children but now family only have one or two. So the number of young people go down but old people number stay same or increase.

The effect of aging population on society is many. First government must spend more money on health for old people. Hospital and medicine cost very expensive. This put pressure on government budget.

Also there is problem with pension. When many old people retire they need money from government. But if less young people work and pay tax there is not enough money for pension. This is serious economic problem.

In my conclusion aging population is caused by better medicine and less birth. The effect include health cost and pension problem for society.',
    5.0,
    'test-seed',
    196,
    TRUE
),
(
    'bbbbbbbb-0004-0004-0004-bbbbbbbbbbbb',
    'ielts_academic',
    'Some people think that a sense of competition in children should be encouraged. Others believe that children who are taught to cooperate rather than compete become more useful adults. Discuss both views.',
    'The question of whether children should compete or cooperate is debate by many people. Both side have argument that I will discuss now.

People who support competition say it prepare children for real world. In adult life we must compete for job and success. If children learn compete when young they will be ready for difficult adult life. Also competition motivate children to work hard and get better result in school.

However other people believe cooperation is more important skill. When people work together they can achieve more than alone. Modern workplace need team work so children must learn cooperate. Also cooperation reduce stress and make learning more enjoy.

I personally think balance is needed between competition and cooperation. Too much competition make children stress and feel bad when they lose. But no competition make children not try hard. Children need learn both skill to become useful adult in modern society.

Both competition and cooperation have value for child development. School and parent should use both method depend on situation. This way children will develop well rounded personality and be prepare for future challenges.',
    5.0,
    'test-seed',
    192,
    TRUE
),
(
    'bbbbbbbb-0005-0005-0005-bbbbbbbbbbbb',
    'ielts_academic',
    'Cities are becoming increasingly crowded. What problems does this cause and what solutions can you suggest?',
    'Cities today have too many people. This cause many problem for people who live there. But there are also some solution we can try.

One big problem of crowded city is traffic. When many people live in city there are too many car on road. Traffic jam make people late for work and waste time. Also many car make air pollution which is bad for health of citizen.

Another problem is housing. When many people come to city house price go up very high. Poor people and young people cannot afford to buy house in city. They must live far from work or in small bad quality house. This is very difficult situation.

Also public service like hospital and school become crowded. When too many people use these service the quality go down. Patient must wait long time in hospital and class in school have too many student.

For solution government can build more public transport so people not use private car. Also government can develop small city outside big city so people not all go to same place. Company can also let employee work from home so less people need travel to city every day.

In conclusion crowded city cause traffic housing and service problem. Good planning and new technology can help solve this problem.',
    4.5,
    'test-seed',
    210,
    TRUE
),
(
    'bbbbbbbb-0006-0006-0006-bbbbbbbbbbbb',
    'ielts_academic',
    'Many people believe that social networking sites such as Facebook have had a huge negative impact on both individuals and society. To what extent do you agree or disagree?',
    'Social network site like Facebook is very popular today. Many people say it have bad effect on people and society. I partly agree with this view.

It is true that social network have some negative impact. Young people spend too much time on these site and not focus on study or real relationship. Also some people share wrong information on social media and this cause problem in society. Cyberbully is also serious problem that happen on social network.

However social network also have positive side that people not mention. It help people stay connect with friend and family who live far away. Before internet people must write letter or make expensive phone call. Now they can communicate free and easy.

Also social network help people find job and business opportunity. Many company use LinkedIn and Facebook to hire people. Small business can advertise on social media without expensive cost. This help economy grow.

I think problem is not social network itself but how people use it. If people use it responsible and in balance way it can be very useful tool. Parent and teacher must educate young people about safe and responsible use of social media.

To conclude social network have both negative and positive impact. It is important that user understand how to use this tool in good way.',
    5.0,
    'test-seed',
    215,
    TRUE
);

-- =================================================================
-- TIER 2: Band 5.5-6.5 — Adequate writers (original 5 essays)
-- =================================================================

INSERT INTO linguamentor.calibration_essays
    (id, exam_type, task_prompt, essay_text, approximate_band, source, word_count, grading_complete)
VALUES
(
    'aaaaaaaa-0001-0001-0001-aaaaaaaaaaaa',
    'ielts_academic',
    'Some people believe that universities should focus only on academic subjects. Others think they should also prepare students for employment. Discuss both views and give your own opinion.',
    'Universities have long been considered centres of academic excellence. However, in recent decades there has been growing debate about whether they should also prepare graduates for the job market. Both perspectives have considerable merit and deserve careful examination.

Those who advocate for a purely academic focus argue that universities exist to advance human knowledge and critical thinking. When institutions prioritise employment training, they risk reducing education to mere vocational instruction. A student studying philosophy or literature, for example, develops analytical skills and cultural understanding that have intrinsic value beyond any particular career path. Furthermore, the skills acquired through rigorous academic study — logical reasoning, research methodology, and written communication — are transferable across many professions.

On the other hand, proponents of career-oriented education point out that most students attend university with employment as a primary goal. With tuition fees rising sharply in many countries, graduates reasonably expect their degrees to translate into better job prospects. Universities that ignore this reality risk leaving students underprepared for the workplace.

In my opinion, the most effective universities strike a balance between these approaches. Core academic disciplines should remain central, but practical modules, internship programmes, and industry partnerships can complement rather than replace traditional scholarship. This balanced model serves both the individual graduate and society as a whole.',
    6.0,
    'test-seed',
    270,
    TRUE
),
(
    'aaaaaaaa-0002-0002-0002-aaaaaaaaaaaa',
    'ielts_academic',
    'The increasing use of technology in education has both advantages and disadvantages. Discuss.',
    'Technology is now widespread in educational settings across the world. While this development offers clear benefits, it also raises important concerns that educators and policymakers must address.

The primary advantage of educational technology is accessibility. Online platforms allow students in remote areas to access high-quality instruction that was previously unavailable to them. Interactive software can also adapt to individual learning speeds, providing personalised feedback that a single teacher managing thirty students cannot realistically offer.

However, the disadvantages are significant. Excessive screen time may harm students concentration and social development. Children who spend long hours on devices may struggle to develop the patience required for deep reading or sustained analytical thinking. Additionally, not all families can afford reliable internet access or modern devices, meaning technology can widen existing educational inequalities rather than reducing them.

There is also the question of teacher skills. Introducing technology without adequate training leads to superficial adoption — teachers use devices as expensive notepads rather than transformative learning tools.

In conclusion, technology enhances education when implemented thoughtfully and equitably. The challenge is ensuring that innovation serves pedagogy rather than replacing the irreplaceable human elements of teaching.',
    6.0,
    'test-seed',
    210,
    TRUE
),
(
    'aaaaaaaa-0003-0003-0003-aaaaaaaaaaaa',
    'ielts_academic',
    'In many countries, the proportion of older people is increasing. What are the causes of this trend and what are the effects on society?',
    'Many developed nations are experiencing a significant demographic shift as the proportion of elderly citizens continues to grow. This essay will examine the primary causes of this trend and consider its implications for society.

The main reason for ageing populations is improved healthcare. Medical advances have extended life expectancy dramatically over the past century. Conditions that were once fatal, such as heart disease and certain cancers, are now manageable chronic illnesses. Simultaneously, birth rates have declined in most wealthy nations as women gain greater access to education and career opportunities, reducing family sizes.

The social effects of this demographic change are far-reaching. Pension systems face mounting pressure as fewer working-age people support a growing number of retirees. Healthcare expenditure rises as older populations require more medical services. Some economists warn of slower economic growth as the workforce shrinks relative to the dependent population.

Nevertheless, older citizens also contribute meaningfully to society. Many remain economically active well into their seventies, while others provide childcare for grandchildren, enabling parents to maintain employment. Their accumulated expertise and institutional knowledge represent a resource that younger generations can draw upon.

Governments must respond with thoughtful policies including pension reform, encouragement of higher birth rates or skilled immigration, and investment in technologies that support independent living for the elderly.',
    6.5,
    'test-seed',
    240,
    TRUE
),
(
    'aaaaaaaa-0004-0004-0004-aaaaaaaaaaaa',
    'ielts_academic',
    'Some people think that a sense of competition in children should be encouraged. Others believe that children who are taught to cooperate rather than compete become more useful adults. Discuss both views.',
    'The question of whether children benefit more from competition or cooperation is widely debated among educators and parents. Both approaches have genuine merits, though the ideal balance depends on context and individual temperament.

Supporters of competitive education argue that it prepares children for adult life. The job market, business environment, and many professional fields are inherently competitive. Children who learn to strive for excellence and handle defeat gracefully are arguably better equipped for these realities. Competition can also motivate students who might otherwise underperform, pushing them toward achievements they would not pursue without external challenge.

Those who favour cooperative learning counter that the most pressing global challenges — climate change, public health crises, international conflict — require collective rather than individual solutions. Children taught to collaborate develop empathy, communication skills, and the ability to subordinate personal interests to group goals. Research in educational psychology suggests that cooperative learning environments often produce stronger academic outcomes than competitive ones, particularly for students from disadvantaged backgrounds.

My view is that both modes have a role in healthy child development. Competition in structured, low-stakes contexts builds resilience. Cooperation in project-based learning builds the interpersonal skills that employers consistently rank among their most valued attributes. The danger lies in either extreme — a purely competitive environment can produce anxiety and individualism, while one that avoids all challenge may leave children unprepared for inevitable adversity.',
    6.5,
    'test-seed',
    265,
    TRUE
),
(
    'aaaaaaaa-0005-0005-0005-aaaaaaaaaaaa',
    'ielts_academic',
    'Cities are becoming increasingly crowded. What problems does this cause and what solutions can you suggest?',
    'Urban populations around the world continue to grow rapidly as people migrate from rural areas in search of employment and better living standards. This concentration of people in cities creates serious challenges that require urgent attention.

The most immediate problem is housing. When demand outpaces supply, property prices and rents rise beyond the reach of ordinary workers, forcing lower-income residents into overcrowded informal settlements on city peripheries. Traffic congestion is another consequence of urban density, reducing productivity and increasing air pollution. Overburdened public services — schools, hospitals, water systems — struggle to meet the needs of rapidly expanding populations.

Several solutions deserve consideration. Investment in public transport infrastructure reduces private vehicle use and makes cities more navigable. Zoning reforms that allow higher-density residential construction near employment centres can ease housing shortages without sprawling outward. Governments can also incentivise businesses to relocate to smaller cities or rural areas, reducing the economic pull factors that drive migration to megacities in the first place.

Ultimately, urban crowding reflects deeper imbalances in how economic opportunities are distributed across a country. Addressing these root causes through regional development policies is more sustainable than managing the symptoms of overcrowding indefinitely.',
    6.5,
    'test-seed',
    225,
    TRUE
);

-- =================================================================
-- TIER 3: Band 7.0 — Competent writers
-- Characteristics: clear position, good range of vocabulary,
-- generally accurate grammar, well-organised paragraphs
-- =================================================================

INSERT INTO linguamentor.calibration_essays
    (id, exam_type, task_prompt, essay_text, approximate_band, source, word_count, grading_complete)
VALUES
(
    'cccccccc-0001-0001-0001-cccccccccccc',
    'ielts_academic',
    'Some people believe that universities should focus only on academic subjects. Others think they should also prepare students for employment. Discuss both views and give your own opinion.',
    'The role of universities in modern society has become a subject of considerable debate. While some argue that higher education institutions should concentrate exclusively on academic and intellectual pursuits, others maintain that preparing students for the workforce is an equally important function. This essay will examine both perspectives before presenting a reasoned position.

Advocates of a purely academic approach contend that universities serve a distinct purpose that differs fundamentally from vocational training. The cultivation of critical thinking, theoretical knowledge, and intellectual curiosity are values that have defined higher education for centuries. When universities begin tailoring their curricula to immediate employment needs, they risk compromising academic integrity and producing graduates who are technically skilled but intellectually underdeveloped. Philosophy, pure mathematics, and classical literature departments have historically produced some of history''s most innovative thinkers precisely because they were free from commercial pressures.

Conversely, the practical argument for employment-focused education is compelling in the contemporary economic context. University education represents a significant financial investment for most students and their families. It is therefore reasonable to expect that this investment translates into tangible career prospects. Furthermore, many employers report that graduates lack basic professional competencies such as project management, communication, and collaborative working — skills that could feasibly be incorporated into university programmes without undermining academic rigour.

In my view, the dichotomy presented in this question is somewhat false. The most successful graduates are those who possess both deep subject knowledge and practical professional skills. Universities should retain their academic core while introducing structured work experience, entrepreneurship programmes, and transferable skills development. This integrated model serves graduates, employers, and society more effectively than either extreme.',
    7.0,
    'test-seed',
    295,
    TRUE
),
(
    'cccccccc-0002-0002-0002-cccccccccccc',
    'ielts_academic',
    'The increasing use of technology in education has both advantages and disadvantages. Discuss.',
    'Digital technology has become deeply embedded in educational systems worldwide, fundamentally changing how knowledge is delivered and acquired. While this transformation offers genuine benefits, it also introduces challenges that deserve serious consideration from educators and policymakers alike.

The advantages of technology in education are well documented. Perhaps most significantly, digital platforms have democratised access to high-quality learning materials, allowing students in geographically isolated or economically disadvantaged regions to access content that was previously available only in well-resourced urban institutions. Adaptive learning software, which adjusts difficulty and content based on individual student performance, offers a degree of personalisation that traditional classroom instruction struggles to achieve given typical class sizes. Moreover, technology facilitates collaborative learning across geographical boundaries, exposing students to diverse perspectives and preparing them for an increasingly globalised professional environment.

However, the drawbacks are equally real. Research consistently shows that excessive screen time is associated with reduced attention spans and impaired executive function in younger learners. There is also growing evidence that passive consumption of digital content — watching videos rather than wrestling with primary texts — may produce surface-level understanding rather than the deep conceptual mastery that education should cultivate. Perhaps most importantly, the unequal distribution of technology access risks exacerbating existing educational inequalities rather than reducing them.

Ultimately, the impact of technology on education depends almost entirely on implementation. Used purposefully as a tool to enhance learning rather than replace teacher expertise, technology can transform educational outcomes. Used carelessly, it may undermine the very cognitive skills that education is designed to develop.',
    7.0,
    'test-seed',
    285,
    TRUE
),
(
    'cccccccc-0003-0003-0003-cccccccccccc',
    'ielts_academic',
    'In many countries, the proportion of older people is increasing. What are the causes of this trend and what are the effects on society?',
    'Demographic ageing represents one of the most significant social transformations of the twenty-first century. The increasing proportion of elderly people in many developed and developing nations is driven by a convergence of factors and carries profound implications for economic organisation, public services, and social structure.

The primary driver of population ageing is the dramatic improvement in life expectancy achieved through medical innovation. Advances in pharmacology, surgical technique, and preventive medicine have transformed conditions that were once fatal into manageable chronic illnesses. Cardiovascular disease, which remains the leading cause of death globally, is increasingly survivable with appropriate medical intervention. Simultaneously, declining fertility rates — driven by increased female participation in higher education and the workforce, improved contraceptive access, and the rising cost of child-rearing in urban environments — have reduced the proportion of younger people in many populations.

The societal effects of this demographic shift are far-reaching. Pension and retirement systems designed when life expectancy was considerably shorter face structural sustainability challenges as the ratio of working-age contributors to retired beneficiaries deteriorates. Healthcare systems must adapt to a patient population with complex, long-term needs rather than acute episodes. Labour markets may experience skill shortages in certain sectors, though this may be partially offset by automation and immigration.

Nevertheless, older populations also represent significant social assets. Accumulated professional expertise, community knowledge, and the capacity for intergenerational mentorship are contributions that cannot be easily quantified but are nonetheless valuable. Policy responses should therefore seek to harness these contributions rather than treating ageing purely as a fiscal problem to be managed.',
    7.0,
    'test-seed',
    280,
    TRUE
),
(
    'cccccccc-0004-0004-0004-cccccccccccc',
    'ielts_academic',
    'Some people think that a sense of competition in children should be encouraged. Others believe that children who are taught to cooperate rather than compete become more useful adults. Discuss both views.',
    'The debate over whether children should be raised in competitive or cooperative environments touches on fundamental questions about human nature, social organisation, and the purpose of education. Both perspectives draw on substantial evidence and reflect genuinely different but defensible visions of what constitutes a well-prepared adult.

Those who favour cultivating competitiveness in children argue that it reflects the reality of adult life in market economies. Professional advancement, academic recognition, and entrepreneurial success all involve competing against others. Children who develop resilience in the face of failure, the motivation to outperform their peers, and the psychological fortitude to handle setbacks are arguably better equipped for the demands of modern working life. Furthermore, competitive environments tend to drive innovation — individuals striving to outperform one another often generate creative solutions that benefit society as a whole.

Proponents of cooperative education draw on a different but equally compelling body of evidence. Developmental psychology research consistently demonstrates that children learn more effectively in collaborative settings, where peer explanation and shared problem-solving deepen understanding more than individual competition. Moreover, the most pressing challenges facing contemporary society — climate change, pandemic preparedness, geopolitical conflict — require collective action and the subordination of individual interests to shared goals. Children who learn empathy, compromise, and collaborative problem-solving may ultimately be better equipped for these realities than those who have been trained to regard others primarily as rivals.

Having considered both perspectives, I believe the most effective developmental approach deliberately combines elements of both. Structured competition builds character and motivation; cooperative projects develop the interpersonal intelligence that employers and communities genuinely need.',
    7.0,
    'test-seed',
    310,
    TRUE
),
(
    'cccccccc-0005-0005-0005-cccccccccccc',
    'ielts_academic',
    'Cities are becoming increasingly crowded. What problems does this cause and what solutions can you suggest?',
    'Rapid urbanisation is one of the defining demographic trends of the modern era, with the United Nations projecting that two-thirds of the world population will live in cities by 2050. This concentration of human activity in urban centres creates a range of interconnected problems that require coordinated responses at multiple levels of governance.

The most pressing consequence of urban overcrowding is the housing crisis that has emerged in major cities across both the developed and developing world. When population growth outpaces residential construction, property values and rental costs escalate beyond the means of lower and middle-income earners, generating social stratification and forcing vulnerable populations into inadequate informal settlements on city peripheries. Compounding this, overwhelmed transport infrastructure produces chronic congestion that reduces economic productivity, increases carbon emissions, and degrades quality of life for commuters. Municipal services including waste management, water supply, and healthcare facilities face similar strain when population growth outpaces investment.

Addressing these challenges requires a multi-pronged policy response. Transit-oriented development — concentrating high-density residential and commercial construction around public transport hubs — can accommodate population growth more efficiently than outward sprawl. Decentralisation policies that incentivise businesses and institutions to relocate to secondary cities can redistribute economic activity more evenly across national territories. At the municipal level, participatory urban planning processes that engage residents in identifying local priorities tend to produce more contextually appropriate and socially accepted solutions than top-down master plans.

None of these interventions will succeed in isolation. Sustainable urban management requires coordinated action across housing, transport, economic and social policy domains simultaneously.',
    7.0,
    'test-seed',
    295,
    TRUE
),
(
    'cccccccc-0006-0006-0006-cccccccccccc',
    'ielts_academic',
    'Many people believe that social networking sites such as Facebook have had a huge negative impact on both individuals and society. To what extent do you agree or disagree?',
    'The assertion that social networking platforms have exerted predominantly negative effects on individuals and society warrants careful scrutiny. While there are legitimate concerns about the consequences of these technologies, a more nuanced assessment suggests that the impact is considerably more complex and context-dependent than the claim implies.

It is undeniable that certain negative consequences of social media use are well-evidenced. Longitudinal studies have linked heavy social media use, particularly among adolescents, with elevated rates of anxiety, depression, and diminished self-esteem, effects that researchers attribute partly to social comparison and partly to the displacement of face-to-face interaction. At the societal level, the algorithmic amplification of emotionally charged content has demonstrably contributed to political polarisation in numerous countries, with filter bubbles limiting exposure to diverse viewpoints and reinforcing pre-existing beliefs.

However, to characterise social networking as predominantly negative is to overlook its substantial benefits. These platforms have enabled unprecedented connectivity, allowing diaspora communities to maintain cultural ties, enabling coordinated civil society action, and providing platforms for marginalised voices that traditional media had systematically excluded. During the COVID-19 pandemic, social media played a crucial role in maintaining social bonds during enforced physical separation. For small businesses and independent creators, these platforms have democratised access to audiences that were previously accessible only through expensive conventional advertising.

I would argue that the platforms themselves are largely neutral instruments whose impact is determined primarily by design choices, regulatory frameworks, and individual usage patterns. The appropriate response is not to condemn social networking categorically but to develop literacy, regulation, and platform design standards that amplify the benefits while mitigating the documented harms.',
    7.0,
    'test-seed',
    315,
    TRUE
);

-- =================================================================
-- TIER 4: Band 7.5-8.0 — Proficient writers
-- =================================================================

INSERT INTO linguamentor.calibration_essays
    (id, exam_type, task_prompt, essay_text, approximate_band, source, word_count, grading_complete)
VALUES
(
    'dddddddd-0001-0001-0001-dddddddddddd',
    'ielts_academic',
    'Some people believe that universities should focus only on academic subjects. Others think they should also prepare students for employment. Discuss both views and give your own opinion.',
    'Few questions in contemporary educational discourse generate more productive disagreement than the proper purpose of universities. The tension between the Humboldtian ideal of education as the pursuit of knowledge for its own sake and the instrumental view of higher education as preparation for economic participation is not merely academic — it shapes curricula, funding priorities, and the lived experience of millions of students worldwide.

The philosophical case for academic purism is not without merit. Universities in the classical tradition were conceived as spaces in which received wisdom could be questioned, where the boundaries of human knowledge might be extended through rigorous inquiry unconstrained by commercial utility. This tradition has yielded extraordinary intellectual dividends: quantum mechanics, evolutionary biology, and the foundations of computing all emerged from theoretical investigations with no immediate practical application. There is a reasonable concern that an academy excessively oriented toward employment may, in optimising for short-term productivity, sacrifice the conditions under which genuine intellectual breakthroughs become possible.

Yet this argument, however intellectually appealing, risks becoming a defence of institutional insularity at the expense of the students whom universities are ostensibly designed to serve. The reality is that the majority of university students are not destined for academic careers; they will enter professions in which theoretical knowledge must be applied within organisational contexts that require collaboration, communication, project management, and adaptability — competencies that traditional academic programmes rarely develop systematically. The argument that such skills are somehow beneath the dignity of academic institutions reflects a class-based hierarchy of knowledge that deserves to be challenged rather than preserved.

My own position is that the framing of this question as a binary choice is itself the problem. Universities that integrate research-led teaching with structured professional development do not sacrifice intellectual rigour; they demonstrate its real-world relevance. The goal should be graduates who are simultaneously capable of independent critical thinking and effective professional practice — characteristics that are complementary rather than contradictory.',
    8.0,
    'test-seed',
    340,
    TRUE
),
(
    'dddddddd-0002-0002-0002-dddddddddddd',
    'ielts_academic',
    'The increasing use of technology in education has both advantages and disadvantages. Discuss.',
    'The integration of digital technology into educational practice has proceeded at a pace that has substantially outrun the evidence base for its effectiveness. This asymmetry between adoption and evaluation is itself instructive: it suggests that enthusiasm for technological innovation in education is driven as much by commercial interest, ideological commitment to modernity, and institutional signalling as by rigorous evidence of improved learning outcomes.

This is not to deny that digital technology has introduced genuinely transformative possibilities into education. The emergence of massive open online courses has extended access to world-class instruction to learners in contexts where physical access to elite institutions is impossible. Adaptive learning systems, when properly designed and implemented, can provide a degree of individualised feedback and progression that no human teacher can replicate at scale. Research tools that would have required weeks of library work a generation ago are now accessible in seconds, potentially accelerating the pace at which students can engage with primary sources and scholarly literature.

However, the critical question is not whether technology can enhance learning under optimal conditions — it clearly can — but whether it does so in practice across the range of contexts and implementations in which it is deployed. The evidence here is considerably more mixed. Studies examining the impact of one-to-one device programmes in schools have found modest or negligible effects on measured academic achievement in many cases. The mechanisms by which technology might harm learning — attention fragmentation, passive consumption displacing active sense-making, social media distraction — are plausible and partially supported by neurological research, even if the magnitude of these effects remains contested.

What the evidence seems to support most clearly is that technology is a powerful amplifier: it amplifies the effectiveness of good pedagogy and the inadequacy of poor pedagogy in equal measure. This suggests that professional development for teachers, rather than hardware procurement, should be the primary focus of educational technology investment.',
    7.5,
    'test-seed',
    350,
    TRUE
),
(
    'dddddddd-0003-0003-0003-dddddddddddd',
    'ielts_academic',
    'In many countries, the proportion of older people is increasing. What are the effects on society?',
    'Population ageing constitutes a structural transformation of such magnitude and duration that its implications extend well beyond the conventional policy domains of healthcare and pension finance. To understand its full significance requires examining not only the fiscal pressures it generates but the ways in which it reconfigures labour markets, intergenerational relationships, political culture, and the very conception of what constitutes a productive or valued social contribution.

The fiscal implications are the most extensively documented. Pay-as-you-go pension systems, designed during periods of high fertility and shorter post-retirement lifespans, face structural imbalances as the dependency ratio deteriorates. Healthcare systems must reorient from episodic acute care toward the management of multiple chronic conditions over extended periods — a model that demands fundamentally different workforce compositions, care delivery architectures, and financing mechanisms. These pressures are real, though they are neither uniformly acute across different national contexts nor entirely without policy solutions.

Less discussed but perhaps equally significant are the implications for labour market structure. Ageing populations in countries without compensatory immigration tend to experience labour shortages in sectors requiring physical capability and willingness to accept demanding working conditions — construction, care work, agriculture. Simultaneously, the growing cohort of healthy, cognitively active people in their sixties and seventies represents an underutilised productive resource that current retirement norms effectively exclude from formal economic participation. The economic case for extending working lives through flexible retirement arrangements and age-inclusive workplace cultures is compelling from both individual and societal perspectives.

Most profoundly, demographic ageing forces a renegotiation of the implicit contract between generations that underlies social solidarity in most societies. How this renegotiation proceeds — whether it produces intergenerational resentment and fiscal conflict or a renewed understanding of mutual obligation across the life course — will depend substantially on the quality of political leadership and public deliberation that accompanies it.',
    8.0,
    'test-seed',
    360,
    TRUE
),
(
    'dddddddd-0004-0004-0004-dddddddddddd',
    'ielts_academic',
    'Some people think that a sense of competition in children should be encouraged. Others believe that children who are taught to cooperate rather than compete become more useful adults. Discuss both views.',
    'The pedagogical question of whether to cultivate competitive or cooperative orientations in children reflects deeper philosophical disagreements about human nature, the good society, and the relationship between individual flourishing and collective welfare. Both positions rest on internally coherent premises and draw on genuine empirical support, making this a genuinely difficult question rather than one admitting of easy resolution.

The case for competition draws its deepest justification from observations about human motivation. Intrinsic motivation — the desire to master skills and achieve goals for their own sake — is powerful but fragile; extrinsic motivators including competitive incentives can maintain effort and engagement in contexts where intrinsic interest is insufficient. Moreover, competitive environments generate information: when children compete, they receive feedback about their relative strengths and weaknesses that enables more accurate self-assessment than purely collaborative settings typically afford. The psychological literature on mastery orientation suggests that children who develop a healthy competitive drive alongside resilience in the face of defeat acquire a motivational architecture that serves them well across diverse life contexts.

Proponents of cooperative education counter that this analysis, while not incorrect, emphasises the wrong unit of analysis. Individual competitive success is a poor proxy for societal benefit when the most valuable outcomes — scientific discovery, democratic governance, community resilience — emerge from collective endeavour rather than individual achievement. Children who develop the capacity to subordinate their immediate interests to shared purposes, to negotiate differences constructively, and to derive satisfaction from collective achievement as well as personal success are arguably better equipped to contribute to these higher-order social goods.

The developmental research suggests a more nuanced synthesis: competition and cooperation are not mutually exclusive but are differentially appropriate across developmental stages and task types. The capacity to modulate between competitive and cooperative orientations as circumstances demand may be the most valuable developmental outcome of all.',
    7.5,
    'test-seed',
    370,
    TRUE
),
(
    'dddddddd-0005-0005-0005-dddddddddddd',
    'ielts_academic',
    'Cities are becoming increasingly crowded. What problems does this cause and what solutions can you suggest?',
    'Urbanisation is simultaneously one of humanity''s greatest achievements and one of its most pressing governance challenges. The concentration of population in cities has historically driven economic development, cultural innovation, and improvements in living standards — yet the pace and scale of contemporary urbanisation in many parts of the world is generating forms of dysfunction that threaten to undermine these benefits.

The problems generated by urban overcrowding are systemic rather than discrete, and their interconnections are as important as any individual manifestation. The housing affordability crisis that afflicts many major cities is not simply a matter of insufficient supply, though that is a significant factor; it reflects the intersection of restrictive zoning codes, speculative investment in residential property, inadequate social housing provision, and the concentration of economic opportunity in a small number of metropolitan centres. Similarly, transport congestion cannot be addressed by road-building alone — it requires integrated approaches to land use, pricing, public transport investment, and remote working arrangements that recognise the relationship between where people live, work, and travel.

The solutions most likely to prove effective share a common characteristic: they address causes rather than symptoms and operate at the level of the urban system rather than individual components. Transit-oriented development, which concentrates density around public transport nodes, simultaneously addresses housing supply, reduces car dependence, and increases the economic viability of public transport investment. Regional development strategies that deliberately cultivate secondary cities as alternatives to primary metropolitan centres can reduce the agglomeration pressures that drive overcrowding in the first place. In rapidly urbanising developing-country contexts, investment in urban planning capacity and land tenure security may generate greater long-term returns than any specific infrastructure intervention.

Ultimately, the cities of the future will be shaped less by the technologies available to planners and more by the political will to make planning decisions that distribute the costs and benefits of urban growth more equitably than current arrangements typically achieve.',
    7.5,
    'test-seed',
    370,
    TRUE
),
(
    'dddddddd-0006-0006-0006-dddddddddddd',
    'ielts_academic',
    'Many people believe that social networking sites such as Facebook have had a huge negative impact on both individuals and society. To what extent do you agree or disagree?',
    'The proposition that social networking platforms have exerted a predominantly negative influence on individuals and society represents a position that is intuitively appealing to many observers but that does not withstand rigorous empirical scrutiny. A more defensible assessment recognises that these technologies have produced heterogeneous effects whose valence depends substantially on the characteristics of users, the contexts of use, and the regulatory and design environments within which platforms operate.

The negative consequences that critics most frequently cite are real and deserve to be taken seriously. The association between intensive social media use and adverse mental health outcomes, particularly among adolescent girls, is supported by a growing body of longitudinal research, even if the causal mechanisms and effect sizes remain subjects of scholarly debate. The algorithmic architecture of major platforms, designed to maximise engagement through the amplification of emotionally activating content, has demonstrably contributed to the spread of misinformation and the intensification of political polarisation in multiple national contexts. These are not trivial concerns.

However, an intellectually honest assessment must acknowledge the countervailing evidence with equal seriousness. Social networking has enabled forms of community formation and collective action that were previously impossible at scale — the coordination of political movements, the organisation of mutual aid networks, the creation of supportive communities for people with rare conditions or marginalised identities who would otherwise experience profound isolation. The platforms have also democratised access to audiences, enabling independent creators, small businesses, and civil society organisations to reach constituents without the intermediation of traditional media gatekeepers whose own record on diversity and inclusion was far from exemplary.

The most intellectually coherent position, in my assessment, is that social networking platforms represent a category of infrastructure whose societal impact is determined primarily by governance choices — concerning algorithmic transparency, data rights, content moderation standards, and market competition — rather than by the technologies themselves. Condemning the platforms categorically forecloses the more productive question of how they should be designed and regulated to serve democratic rather than purely commercial ends.',
    8.0,
    'test-seed',
    390,
    TRUE
);

-- =================================================================
-- TIER 5: Band 8.5 — Near-expert writers
-- =================================================================

INSERT INTO linguamentor.calibration_essays
    (id, exam_type, task_prompt, essay_text, approximate_band, source, word_count, grading_complete)
VALUES
(
    'eeeeeeee-0001-0001-0001-eeeeeeeeeeee',
    'ielts_academic',
    'Some people believe that universities should focus only on academic subjects. Others think they should also prepare students for employment. Discuss both views and give your own opinion.',
    'The perennial debate over the proper purpose of universities conceals a more fundamental question about what kind of society we wish to inhabit and what kind of human beings we wish to cultivate. When we ask whether universities should be academically pure or vocationally oriented, we are ultimately asking about the relationship between knowledge and power, between individual flourishing and economic utility, between the short-term demands of labour markets and the long-term interests of civilisation.

The philosophical tradition that privileges academic freedom and the disinterested pursuit of knowledge can invoke an impressive genealogy. From the mediaeval studium generale through the Enlightenment republic of letters to the research universities of the nineteenth century, the argument has been that knowledge pursued without regard for immediate utility tends, paradoxically, to generate the most transformative practical applications in the long run. The basic research programmes of twentieth-century physics, seemingly remote from practical application, gave rise to computing, nuclear energy, and medical imaging technologies. This argument is not merely historical sentiment; it reflects a genuine insight about the conditions under which genuine intellectual breakthrough becomes possible.

Yet this tradition has often served as a convenient rationale for institutional conservatism and social exclusion. The ideal of the disinterested scholar pursuing knowledge for its own sake has historically been most available to those who did not need to work for a living — a circumstance that explains the demographic homogeneity that has characterised universities throughout most of their history. When we ask whether universities should prepare students for employment, we are partly asking whether higher education should serve its traditional clientele of the economically secure or the much broader population that mass higher education systems now enrol.

My view is that this tension cannot be dissolved by institutional design but only by a prior commitment to what higher education is fundamentally for. If it is for the development of human capabilities in the fullest sense — cognitive, ethical, creative, and practical — then there is no genuine contradiction between intellectual rigour and professional preparation. The challenge is to resist the reduction of professional preparation to narrow credentialism, which would genuinely compromise the academic mission, while ensuring that the academy''s legitimate intellectual ambitions do not become a pretext for failing the students it is supposed to serve.',
    8.5,
    'test-seed',
    400,
    TRUE
),
(
    'eeeeeeee-0002-0002-0002-eeeeeeeeeeee',
    'ielts_academic',
    'The increasing use of technology in education has both advantages and disadvantages. Discuss.',
    'The question of technology in education is rarely posed with sufficient precision to admit of a useful answer. Technology is not a single phenomenon but an extraordinarily heterogeneous category encompassing everything from the printed book — itself a disruptive technology when first introduced to educational settings — to artificial intelligence systems that can generate, evaluate, and personalise instructional content in real time. The claim that technology in education has advantages and disadvantages is trivially true of virtually any significant educational innovation; the more productive questions concern which technologies, under what conditions, for which learners and purposes, produce what kinds of outcomes.

With this caveat established, certain generalisations do appear to be reasonably well supported by the available evidence. Digital technologies that enhance access to high-quality instructional resources for learners who would otherwise be deprived of them represent an unambiguous social benefit, even if their effects on individual learning outcomes are difficult to isolate from confounding variables. The extension of educational opportunity to populations previously excluded by geography, disability, or economic circumstance is a significant achievement by any reasonable metric of social justice, and digital technology has been an indispensable enabler of this extension.

The concerns about technology in education are more varied and contextually dependent. The neurological research on attention — demonstrating that the capacity for sustained, deep engagement with complex material is itself a cultivated cognitive skill that can be degraded by habitual multitasking and the consumption of short-form content — raises questions about whether the informational abundance facilitated by digital technology may, in certain conditions, undermine the very cognitive capacities that educational institutions are designed to develop. These concerns are most acute for younger learners whose attentional and metacognitive capacities are still developing.

The most intellectually honest conclusion is that technology in education is neither inherently beneficial nor inherently harmful but is a powerful amplifier of existing pedagogical practices and institutional cultures. Institutions with strong pedagogical traditions, well-trained teachers, and clear educational purposes will use technology effectively; those without these foundations will not. Investment in professional development and pedagogical research is therefore more likely to improve educational outcomes than investment in technology per se.',
    8.5,
    'test-seed',
    410,
    TRUE
),
(
    'eeeeeeee-0003-0003-0003-eeeeeeeeeeee',
    'ielts_academic',
    'In many countries, the proportion of older people is increasing. What are the causes of this trend and what are the effects on society?',
    'Population ageing is best understood not as a problem to be solved but as a structural condition to be navigated — one that reflects the success of twentieth-century public health and medical science in extending human lifespans while simultaneously posing challenges for institutions and social arrangements designed under the assumption of very different demographic realities.

The demographic transition that underlies population ageing follows a well-established pattern: as societies develop economically and socially, mortality rates fall first, then fertility rates follow with a lag of several generations. The result is a temporary demographic dividend — a period during which a large working-age cohort supports relatively small dependent populations at both ends of the age spectrum — followed by an ageing phase as the large cohorts of the transition period reach retirement age and below-replacement fertility reduces the relative size of younger cohorts. Understanding that ageing is an almost universal feature of development, rather than a pathology specific to certain societies, is important for calibrating appropriate policy responses.

The fiscal implications — rising healthcare costs, pension system sustainability, changing dependency ratios — have received extensive scholarly and policy attention. Less discussed is the potential for population ageing to reshape political culture in ways that may be more consequential in the long run. Older populations tend to vote at higher rates than younger ones, potentially shifting political priorities toward the preservation of existing assets and entitlements rather than investment in future-oriented public goods. The intergenerational equity implications of this dynamic deserve more systematic attention than they typically receive in policy discourse that treats population ageing primarily as a budgetary challenge.

The societal effects of population ageing will ultimately be determined less by the demographic facts themselves than by the institutional, cultural, and political responses they elicit. Societies that develop flexible labour market arrangements, sustainable long-term care systems, and cultures of intergenerational solidarity will navigate this transition with considerably less disruption than those that treat it primarily as a fiscal inconvenience to be managed through austerity.',
    8.5,
    'test-seed',
    390,
    TRUE
),
(
    'eeeeeeee-0004-0004-0004-eeeeeeeeeeee',
    'ielts_academic',
    'Some people think that a sense of competition in children should be encouraged. Others believe that children who are taught to cooperate rather than compete become more useful adults. Discuss both views.',
    'The competition-cooperation dichotomy, as applied to child development, reflects a broader tension in liberal democratic thought between conceptions of human beings as fundamentally self-interested agents whose interactions are best organised through competitive markets and conceptions of human beings as fundamentally social creatures whose capacities are most fully realised through cooperative endeavour. Neither conception adequately captures the complexity of human motivation, and neither developmental approach, pursued exclusively, is likely to produce the psychologically integrated, socially capable adults that families, communities, and employers actually need.

The psychological case for competitive environments draws its strongest support from self-determination theory and research on achievement motivation. Under conditions that support autonomy and competence, competition can enhance intrinsic motivation by providing clear performance feedback and the satisfaction of mastery. Elite athletic and academic programmes demonstrate that competitive environments can be psychologically healthy when they emphasise personal improvement relative to previous performance rather than zero-sum ranking — a distinction that is often overlooked in popular discussions of competition in education.

The developmental case for cooperation is grounded in different but equally robust evidence. Vygotsky''s work on the zone of proximal development established that children learn most effectively through guided interaction with more capable peers — a fundamentally cooperative rather than competitive process. More recent research in social neuroscience has demonstrated that collaborative problem-solving activates reward circuitry in ways that solo achievement does not, suggesting that cooperation is not merely instrumentally valuable but constitutively satisfying in ways that have been underweighted in educational design.

What the evidence collectively suggests is not that one approach is superior but that developmental resilience requires exposure to both. Children who have learned to compete with grace — to strive ambitiously without defining their worth by comparative ranking — and to cooperate genuinely — to subordinate immediate self-interest to shared purpose without losing their individual initiative — are better equipped for the genuine complexity of adult life than those trained exclusively in either orientation. The pedagogical challenge is to create learning environments sophisticated enough to develop both capacities simultaneously.',
    8.5,
    'test-seed',
    400,
    TRUE
),
(
    'eeeeeeee-0005-0005-0005-eeeeeeeeeeee',
    'ielts_academic',
    'Cities are becoming increasingly crowded. What problems does this cause and what solutions can you suggest?',
    'The contemporary urban crisis is, at its most fundamental level, a crisis of governance — a failure of political institutions and planning systems to manage the spatial organisation of human activity in ways that distribute the costs and benefits of urban agglomeration more equitably across social groups and generations. Technical solutions exist for virtually every specific manifestation of urban overcrowding; the binding constraint is not knowledge or technology but the political economy of urban development, which systematically advantages those who benefit from the status quo over those who bear its costs.

The problems generated by rapid urbanisation are well documented but insufficiently understood in their systemic interconnection. Housing unaffordability in global cities is not primarily a consequence of insufficient supply, though supply constraints are real; it reflects the transformation of residential property from a social good into a financial asset class, a process that has been actively facilitated by macroeconomic policies favouring asset price inflation and tax regimes that favour capital gains over wage income. Traffic congestion similarly reflects not merely inadequate infrastructure but a century of land use regulation and infrastructure investment that has systematically subsidised car-dependent development patterns while allowing the true costs of private vehicle use — congestion, pollution, road casualties, urban fragmentation — to be socialised rather than internalised by users.

The solutions most likely to prove durable share several characteristics: they address incentive structures rather than outcomes, they operate at the level of urban systems rather than individual components, and they are designed to be adaptive rather than optimal for a fixed set of conditions. Land value capture mechanisms that allow municipalities to recoup a share of the land value uplift generated by public infrastructure investment can fund the services that growing populations require without relying entirely on general taxation. Inclusive planning processes that give affected communities genuine agency over development decisions can improve the quality of outcomes while building the social legitimacy that large-scale urban transformation requires. Digital infrastructure that enables high-quality remote work arrangements can reduce the agglomeration pressures that drive overcrowding in the first place.

The cities that will be most liveable in 2050 are likely to be those that use the current period of technological and institutional flux not merely to solve present problems more efficiently but to reconfigure the underlying incentive structures that generate those problems — a task that requires political imagination and institutional courage rather than technical expertise alone.',
    8.5,
    'test-seed',
    430,
    TRUE
),
(
    'eeeeeeee-0006-0006-0006-eeeeeeeeeeee',
    'ielts_academic',
    'Many people believe that social networking sites such as Facebook have had a huge negative impact on both individuals and society. To what extent do you agree or disagree?',
    'The moral panic surrounding social networking platforms exhibits many of the characteristic features of earlier episodes of technological anxiety — the printing press, the novel, the telegraph, television — in which a new communications medium was held responsible for the degradation of individual character and social cohesion by commentators who typically had limited understanding of the medium and its actual patterns of use. This historical observation does not settle the question of whether social media has been net beneficial or harmful — history also records cases in which new technologies did produce significant negative consequences — but it should induce appropriate epistemic humility about confident negative assessments.

The empirical evidence on the psychological effects of social media use is considerably more ambiguous than public discourse typically acknowledges. The association between social media use and poor mental health outcomes in adolescents, widely cited in media coverage, is based primarily on cross-sectional studies with substantial methodological limitations; longitudinal research and studies using experience sampling methods have produced more mixed results, with effect sizes that are often small by conventional standards. This does not mean the concern is unfounded — small average effects can mask large effects for vulnerable subgroups, and the mechanisms by which social media might harm mental health are plausible — but it cautions against the kind of categorical negative assessment that the question''s framing invites.

The societal effects of social networking are similarly complex. The platforms have unquestionably been implicated in the spread of health misinformation, the amplification of political extremism, and the coordination of harassment campaigns against individual targets. These are serious harms. But the same infrastructure has enabled civil society mobilisation, facilitated mutual aid in crises, provided community for isolated individuals, and created economic opportunity for people excluded from traditional labour and capital markets. A technology that simultaneously does all of these things resists straightforward moral categorisation.

The most intellectually responsible position, in my assessment, holds that the net societal impact of social networking platforms is an open empirical question that depends on design choices, regulatory frameworks, and social practices that are themselves mutable. The productive response to documented harms is not condemnation but reform — of platform architectures, of data governance regimes, of the educational practices that shape how people engage with digital information — aimed at preserving the genuine benefits while mitigating the genuine costs.',
    8.5,
    'test-seed',
    420,
    TRUE
);

-- =================================================================
-- HUMAN SCORES — All 30 essays, 2 examiners each
-- Examiner A: conservative (within 0.5 of band level)
-- Examiner B: slightly generous (within 0.5 of band level)
-- Mirrors real IELTS inter-rater reliability patterns
-- =================================================================

-- TIER 1: Band 4.5-5.0
INSERT INTO linguamentor.calibration_human_scores
    (id, essay_id, examiner_id, score_task_response, score_coherence_cohesion, score_lexical_resource, score_grammatical_range, score_overall, is_adjudicating)
VALUES
    (uuid_generate_v4(), 'bbbbbbbb-0001-0001-0001-bbbbbbbbbbbb', 'examiner-A', 4.5, 4.5, 4.5, 4.0, 4.5, FALSE),
    (uuid_generate_v4(), 'bbbbbbbb-0001-0001-0001-bbbbbbbbbbbb', 'examiner-B', 5.0, 4.5, 4.5, 4.5, 4.5, FALSE),
    (uuid_generate_v4(), 'bbbbbbbb-0002-0002-0002-bbbbbbbbbbbb', 'examiner-A', 4.5, 4.0, 4.5, 4.0, 4.5, FALSE),
    (uuid_generate_v4(), 'bbbbbbbb-0002-0002-0002-bbbbbbbbbbbb', 'examiner-B', 4.5, 4.5, 4.5, 4.5, 4.5, FALSE),
    (uuid_generate_v4(), 'bbbbbbbb-0003-0003-0003-bbbbbbbbbbbb', 'examiner-A', 5.0, 4.5, 4.5, 4.5, 5.0, FALSE),
    (uuid_generate_v4(), 'bbbbbbbb-0003-0003-0003-bbbbbbbbbbbb', 'examiner-B', 5.0, 5.0, 5.0, 4.5, 5.0, FALSE),
    (uuid_generate_v4(), 'bbbbbbbb-0004-0004-0004-bbbbbbbbbbbb', 'examiner-A', 5.0, 4.5, 4.5, 4.5, 5.0, FALSE),
    (uuid_generate_v4(), 'bbbbbbbb-0004-0004-0004-bbbbbbbbbbbb', 'examiner-B', 5.0, 5.0, 5.0, 5.0, 5.0, FALSE),
    (uuid_generate_v4(), 'bbbbbbbb-0005-0005-0005-bbbbbbbbbbbb', 'examiner-A', 4.5, 4.5, 4.5, 4.0, 4.5, FALSE),
    (uuid_generate_v4(), 'bbbbbbbb-0005-0005-0005-bbbbbbbbbbbb', 'examiner-B', 5.0, 4.5, 5.0, 4.5, 5.0, FALSE),
    (uuid_generate_v4(), 'bbbbbbbb-0006-0006-0006-bbbbbbbbbbbb', 'examiner-A', 5.0, 4.5, 5.0, 4.5, 5.0, FALSE),
    (uuid_generate_v4(), 'bbbbbbbb-0006-0006-0006-bbbbbbbbbbbb', 'examiner-B', 5.0, 5.0, 5.0, 5.0, 5.0, FALSE);

-- TIER 2: Band 5.5-6.5
INSERT INTO linguamentor.calibration_human_scores
    (id, essay_id, examiner_id, score_task_response, score_coherence_cohesion, score_lexical_resource, score_grammatical_range, score_overall, is_adjudicating)
VALUES
    (uuid_generate_v4(), 'aaaaaaaa-0001-0001-0001-aaaaaaaaaaaa', 'examiner-A', 6.0, 6.0, 6.0, 5.5, 6.0, FALSE),
    (uuid_generate_v4(), 'aaaaaaaa-0001-0001-0001-aaaaaaaaaaaa', 'examiner-B', 6.0, 6.5, 6.0, 6.0, 6.0, FALSE),
    (uuid_generate_v4(), 'aaaaaaaa-0002-0002-0002-aaaaaaaaaaaa', 'examiner-A', 6.0, 5.5, 6.0, 5.5, 6.0, FALSE),
    (uuid_generate_v4(), 'aaaaaaaa-0002-0002-0002-aaaaaaaaaaaa', 'examiner-B', 6.0, 6.0, 6.0, 6.0, 6.0, FALSE),
    (uuid_generate_v4(), 'aaaaaaaa-0003-0003-0003-aaaaaaaaaaaa', 'examiner-A', 6.5, 6.5, 6.5, 6.0, 6.5, FALSE),
    (uuid_generate_v4(), 'aaaaaaaa-0003-0003-0003-aaaaaaaaaaaa', 'examiner-B', 7.0, 6.5, 6.5, 6.5, 6.5, FALSE),
    (uuid_generate_v4(), 'aaaaaaaa-0004-0004-0004-aaaaaaaaaaaa', 'examiner-A', 6.5, 6.5, 6.5, 6.0, 6.5, FALSE),
    (uuid_generate_v4(), 'aaaaaaaa-0004-0004-0004-aaaaaaaaaaaa', 'examiner-B', 6.5, 7.0, 6.5, 6.5, 6.5, FALSE),
    (uuid_generate_v4(), 'aaaaaaaa-0005-0005-0005-aaaaaaaaaaaa', 'examiner-A', 6.5, 6.0, 6.5, 6.0, 6.5, FALSE),
    (uuid_generate_v4(), 'aaaaaaaa-0005-0005-0005-aaaaaaaaaaaa', 'examiner-B', 6.5, 6.5, 6.5, 6.5, 6.5, FALSE);

-- TIER 3: Band 7.0
INSERT INTO linguamentor.calibration_human_scores
    (id, essay_id, examiner_id, score_task_response, score_coherence_cohesion, score_lexical_resource, score_grammatical_range, score_overall, is_adjudicating)
VALUES
    (uuid_generate_v4(), 'cccccccc-0001-0001-0001-cccccccccccc', 'examiner-A', 7.0, 7.0, 7.0, 6.5, 7.0, FALSE),
    (uuid_generate_v4(), 'cccccccc-0001-0001-0001-cccccccccccc', 'examiner-B', 7.0, 7.0, 7.0, 7.0, 7.0, FALSE),
    (uuid_generate_v4(), 'cccccccc-0002-0002-0002-cccccccccccc', 'examiner-A', 7.0, 6.5, 7.0, 6.5, 7.0, FALSE),
    (uuid_generate_v4(), 'cccccccc-0002-0002-0002-cccccccccccc', 'examiner-B', 7.0, 7.0, 7.0, 7.0, 7.0, FALSE),
    (uuid_generate_v4(), 'cccccccc-0003-0003-0003-cccccccccccc', 'examiner-A', 7.0, 7.0, 6.5, 7.0, 7.0, FALSE),
    (uuid_generate_v4(), 'cccccccc-0003-0003-0003-cccccccccccc', 'examiner-B', 7.5, 7.0, 7.0, 7.0, 7.0, FALSE),
    (uuid_generate_v4(), 'cccccccc-0004-0004-0004-cccccccccccc', 'examiner-A', 7.0, 7.0, 7.0, 6.5, 7.0, FALSE),
    (uuid_generate_v4(), 'cccccccc-0004-0004-0004-cccccccccccc', 'examiner-B', 7.0, 7.0, 7.0, 7.0, 7.0, FALSE),
    (uuid_generate_v4(), 'cccccccc-0005-0005-0005-cccccccccccc', 'examiner-A', 7.0, 7.0, 7.0, 6.5, 7.0, FALSE),
    (uuid_generate_v4(), 'cccccccc-0005-0005-0005-cccccccccccc', 'examiner-B', 7.0, 7.5, 7.0, 7.0, 7.0, FALSE),
    (uuid_generate_v4(), 'cccccccc-0006-0006-0006-cccccccccccc', 'examiner-A', 7.0, 7.0, 7.0, 7.0, 7.0, FALSE),
    (uuid_generate_v4(), 'cccccccc-0006-0006-0006-cccccccccccc', 'examiner-B', 7.0, 7.0, 7.5, 7.0, 7.0, FALSE);

-- TIER 4: Band 7.5-8.0
INSERT INTO linguamentor.calibration_human_scores
    (id, essay_id, examiner_id, score_task_response, score_coherence_cohesion, score_lexical_resource, score_grammatical_range, score_overall, is_adjudicating)
VALUES
    (uuid_generate_v4(), 'dddddddd-0001-0001-0001-dddddddddddd', 'examiner-A', 8.0, 7.5, 8.0, 7.5, 8.0, FALSE),
    (uuid_generate_v4(), 'dddddddd-0001-0001-0001-dddddddddddd', 'examiner-B', 8.0, 8.0, 8.0, 8.0, 8.0, FALSE),
    (uuid_generate_v4(), 'dddddddd-0002-0002-0002-dddddddddddd', 'examiner-A', 7.5, 7.5, 7.5, 7.5, 7.5, FALSE),
    (uuid_generate_v4(), 'dddddddd-0002-0002-0002-dddddddddddd', 'examiner-B', 7.5, 8.0, 7.5, 7.5, 7.5, FALSE),
    (uuid_generate_v4(), 'dddddddd-0003-0003-0003-dddddddddddd', 'examiner-A', 8.0, 8.0, 7.5, 8.0, 8.0, FALSE),
    (uuid_generate_v4(), 'dddddddd-0003-0003-0003-dddddddddddd', 'examiner-B', 8.0, 8.0, 8.0, 8.0, 8.0, FALSE),
    (uuid_generate_v4(), 'dddddddd-0004-0004-0004-dddddddddddd', 'examiner-A', 7.5, 7.5, 7.5, 7.5, 7.5, FALSE),
    (uuid_generate_v4(), 'dddddddd-0004-0004-0004-dddddddddddd', 'examiner-B', 8.0, 7.5, 7.5, 7.5, 7.5, FALSE),
    (uuid_generate_v4(), 'dddddddd-0005-0005-0005-dddddddddddd', 'examiner-A', 7.5, 7.5, 7.5, 7.5, 7.5, FALSE),
    (uuid_generate_v4(), 'dddddddd-0005-0005-0005-dddddddddddd', 'examiner-B', 7.5, 8.0, 8.0, 7.5, 7.5, FALSE),
    (uuid_generate_v4(), 'dddddddd-0006-0006-0006-dddddddddddd', 'examiner-A', 8.0, 7.5, 8.0, 7.5, 8.0, FALSE),
    (uuid_generate_v4(), 'dddddddd-0006-0006-0006-dddddddddddd', 'examiner-B', 8.0, 8.0, 8.0, 8.0, 8.0, FALSE);

-- TIER 5: Band 8.5
INSERT INTO linguamentor.calibration_human_scores
    (id, essay_id, examiner_id, score_task_response, score_coherence_cohesion, score_lexical_resource, score_grammatical_range, score_overall, is_adjudicating)
VALUES
    (uuid_generate_v4(), 'eeeeeeee-0001-0001-0001-eeeeeeeeeeee', 'examiner-A', 8.5, 8.5, 8.5, 8.0, 8.5, FALSE),
    (uuid_generate_v4(), 'eeeeeeee-0001-0001-0001-eeeeeeeeeeee', 'examiner-B', 9.0, 8.5, 8.5, 8.5, 8.5, FALSE),
    (uuid_generate_v4(), 'eeeeeeee-0002-0002-0002-eeeeeeeeeeee', 'examiner-A', 8.5, 8.5, 8.5, 8.5, 8.5, FALSE),
    (uuid_generate_v4(), 'eeeeeeee-0002-0002-0002-eeeeeeeeeeee', 'examiner-B', 8.5, 9.0, 8.5, 8.5, 8.5, FALSE),
    (uuid_generate_v4(), 'eeeeeeee-0003-0003-0003-eeeeeeeeeeee', 'examiner-A', 8.5, 8.0, 8.5, 8.5, 8.5, FALSE),
    (uuid_generate_v4(), 'eeeeeeee-0003-0003-0003-eeeeeeeeeeee', 'examiner-B', 8.5, 8.5, 8.5, 8.5, 8.5, FALSE),
    (uuid_generate_v4(), 'eeeeeeee-0004-0004-0004-eeeeeeeeeeee', 'examiner-A', 8.5, 8.5, 8.0, 8.5, 8.5, FALSE),
    (uuid_generate_v4(), 'eeeeeeee-0004-0004-0004-eeeeeeeeeeee', 'examiner-B', 9.0, 8.5, 8.5, 8.5, 8.5, FALSE),
    (uuid_generate_v4(), 'eeeeeeee-0005-0005-0005-eeeeeeeeeeee', 'examiner-A', 8.5, 8.5, 8.5, 8.5, 8.5, FALSE),
    (uuid_generate_v4(), 'eeeeeeee-0005-0005-0005-eeeeeeeeeeee', 'examiner-B', 8.5, 8.5, 9.0, 8.5, 8.5, FALSE),
    (uuid_generate_v4(), 'eeeeeeee-0006-0006-0006-eeeeeeeeeeee', 'examiner-A', 8.5, 8.5, 8.5, 8.0, 8.5, FALSE),
    (uuid_generate_v4(), 'eeeeeeee-0006-0006-0006-eeeeeeeeeeee', 'examiner-B', 8.5, 9.0, 8.5, 8.5, 8.5, FALSE);

-- =================================================================
-- Verification
-- =================================================================
SELECT approximate_band, COUNT(*) as essay_count
FROM linguamentor.calibration_essays
WHERE source = 'test-seed'
GROUP BY approximate_band
ORDER BY approximate_band;

SELECT COUNT(*) as total_essays FROM linguamentor.calibration_essays WHERE source = 'test-seed';
SELECT COUNT(*) as total_human_scores FROM linguamentor.calibration_human_scores
WHERE essay_id IN (SELECT id FROM linguamentor.calibration_essays WHERE source = 'test-seed');
