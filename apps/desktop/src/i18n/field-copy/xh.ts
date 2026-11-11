// Hand-authored isiXhosa settings copy. Keys match app/settings/constants.ts.
// Product names, option values, protocol identifiers and audio tags stay verbatim.
import { defineFieldCopy } from '@/app/settings/field-copy'

export const FIELD_LABELS: Record<string, string> = defineFieldCopy({
  model: 'Imodeli yokungagqibekanga',
  modelContextLength: 'Ifestile yomxholo',
  fallbackProviders: 'Iimodeli zokugcina',
  toolsets: 'Iiseti zezixhobo ezivuliweyo',
  timezone: 'Ummandla wexesha',
  display: {
    personality: 'Ubuntu',
    showReasoning: 'Amacandelo okuqiqa',
  },
  desktop: {
    repoScanEnabled: 'Ukufunyanwa koovimba ngokuzenzekelayo',
    repoScanRoots: 'Iifolda zokuqala ukukhangela oovimba',
    repoScanExcludePaths: 'Iindlela zoovimba ezingabandakanywanga',
  },
  agent: {
    maxTurns: 'Elona nani likhulu lamanyathelo e-arhente',
    imageInputMode: 'Izincamatheliso zemifanekiso',
    apiMaxRetries: 'Ukuzama kwakhona kwe-API',
    serviceTier: 'Inqanaba lenkonzo',
    toolUseEnforcement: 'Ukunyanzeliswa kokusetyenziswa kwezixhobo',
  },
  terminal: {
    cwd: 'Ifolda yokusebenza',
    backend: 'Inkonzo yokuqhuba',
    timeout: 'Ixesha elivumelekileyo lomyalelo',
    persistentShell: 'Iqokobhe eligcina imeko',
    envPassthrough: 'Ukudluliswa kweziguquguquki zemeko-bume',
    dockerImage: 'Umfanekiso we-Docker',
    singularityImage: 'Umfanekiso we-Singularity',
    modalImage: 'Umfanekiso we-Modal',
    daytonaImage: 'Umfanekiso we-Daytona',
  },
  fileReadMaxChars: 'Umda wokufunda ifayile',
  toolOutput: {
    maxBytes: 'Umda wemveliso yetheminali',
    maxLines: 'Umda wephepha lefayile',
    maxLineLength: 'Umda wobude bomgca',
  },
  codeExecution: {
    mode: 'Indlela yokuqhuba ikhowudi',
  },
  approvals: {
    mode: 'Indlela yokuvuma',
    timeout: 'Ixesha elivumelekileyo lokuvuma',
    mcpReloadConfirm: 'Qinisekisa ukulayishwa kwakhona kwe-MCP',
  },
  commandAllowlist: 'Uluhlu lwemiyalelo evumelekileyo',
  security: {
    redactSecrets: 'Fihla iimfihlo',
    allowPrivateUrls: 'Vumela ii-URL zabucala',
  },
  browser: {
    allowPrivateUrls: 'Ii-URL zabucala zebhrawuza',
    autoLocalForPrivateUrls: 'Ibhrawuza yendawo yee-URL zabucala',
  },
  checkpoints: {
    enabled: 'Iindawo zokubuyisela iifayile',
    maxSnapshots: 'Umda weendawo zokubuyisela',
  },
  voice: {
    recordKey: 'Indlela emfutshane yelizwi',
    maxRecordingSeconds: 'Obona bude bukhulu boshicilelo',
    autoTts: 'Funda iimpendulo ngokuvakalayo',
  },
  stt: {
    enabled: 'Ukuguqula intetho ibe ngumbhalo',
    echoTranscripts: 'Phinda uthumele imibhalo yentetho',
    provider: 'Umnikezeli wokuguqula intetho ibe ngumbhalo',
    local: {
      model: 'Imodeli yendawo yokubhala intetho',
      language: 'Ulwimi lokubhala intetho',
    },
    openai: { model: 'Imodeli ye-STT ye-OpenAI' },
    groq: { model: 'Imodeli ye-STT ye-Groq' },
    mistral: { model: 'Imodeli ye-STT ye-Mistral' },
    elevenlabs: {
      modelId: 'Imodeli ye-STT ye-ElevenLabs',
      languageCode: 'Ulwimi lwe-ElevenLabs',
      tagAudioEvents: 'Phawula iziganeko zesandi',
      diarize: 'Ukwahlula izithethi',
    },
  },
  tts: {
    provider: 'Umnikezeli wokuguqula umbhalo ube yintetho',
    edge: { voice: 'Ilizwi le-Edge' },
    openai: {
      model: 'Imodeli ye-TTS ye-OpenAI',
      voice: 'Ilizwi le-OpenAI',
    },
    elevenlabs: {
      voiceId: 'Ilizwi le-ElevenLabs',
      modelId: 'Imodeli ye-ElevenLabs',
    },
    xai: {
      voiceId: 'Ilizwi le-xAI (Grok)',
      language: 'Ulwimi lwe-xAI',
      speed: 'Isantya sokudlala se-xAI',
      autoSpeechTags: 'Iithegi zentetho ezizenzekelayo ze-xAI',
      optimizeStreamingLatency: 'Ukunciphisa ukulibaziseka kokusasaza kwe-xAI',
      sampleRate: 'Iqondo lokuthatha iisampulu le-xAI',
      bitRate: 'Iqondo lamasuntswana le-xAI',
    },
    minimax: {
      model: 'Imodeli ye-TTS ye-MiniMax',
      voiceId: 'Ilizwi le-MiniMax',
    },
    mistral: {
      model: 'Imodeli ye-TTS ye-Mistral',
      voiceId: 'Ilizwi le-Mistral',
    },
    gemini: {
      model: 'Imodeli ye-TTS ye-Gemini',
      voice: 'Ilizwi le-Gemini',
    },
    neutts: {
      model: 'Imodeli ye-NeuTTS',
      device: 'Isixhobo se-NeuTTS',
    },
    kittentts: {
      model: 'Imodeli ye-KittenTTS',
      voice: 'Ilizwi le-KittenTTS',
    },
    piper: { voice: 'Ilizwi le-Piper' },
    deepinfra: {
      model: 'Imodeli ye-TTS ye-DeepInfra',
      voice: 'Ilizwi le-DeepInfra',
    },
  },
  memory: {
    memoryEnabled: 'Inkumbulo esisigxina',
    userProfileEnabled: 'Iprofayile yomsebenzisi',
    memoryCharLimit: 'Umda wenkumbulo',
    userCharLimit: 'Umda weprofayile',
    provider: 'Umnikezeli wenkumbulo',
  },
  context: { engine: 'Injini yomxholo' },
  compression: {
    enabled: 'Ukucinezela ngokuzenzekelayo',
    threshold: 'Inqanaba lokuqalisa ukucinezela',
    targetRatio: 'Umlinganiselo ekujoliswe kuwo wokucinezela',
    protectLastN: 'Imiyalezo yakutshanje ekhuselweyo',
  },
  delegation: {
    model: 'Imodeli ye-arhente encedisayo',
    provider: 'Umnikezeli we-arhente encedisayo',
    maxIterations: 'Umda wamathuba e-arhente encedisayo',
    maxConcurrentChildren: 'Ii-arhente ezincedisayo ngaxeshanye',
    childTimeoutSeconds: 'Ixesha elivumelekileyo le-arhente encedisayo',
    reasoningEffort: 'Umzamo wokuqiqa we-arhente encedisayo',
  },
  updates: { nonInteractiveLocalChanges: 'Utshintsho lwendawo xa kuhlaziywa kusetyenziso' },
})

export const FIELD_DESCRIPTIONS: Record<string, string> = defineFieldCopy({
  model: 'Isetyenziswa kwiincoko ezintsha ngaphandle kokuba ukhethe enye imodeli kwindawo yokubhala.',
  modelContextLength: 'Shiya ku-0 ukuze usebenzise ifestile yomxholo efunyenweyo yemodeli ekhethiweyo.',
  fallbackProviders: 'Amangeniso e-provider:model aza kuzanywa ukuba imodeli yokungagqibekanga iyasilela.',
  display: {
    personality: 'Indlela yomncedisi yokungagqibekanga kwiiseshoni ezintsha.',
    showReasoning: 'Bonisa amacandelo okuqiqa xa inkonzo yangasemva iwabonelela.',
  },
  desktop: {
    repoScanEnabled: 'Khangela oovimba be-Git kwiifolda zendawo ukuze baboniswe kwiiProjekthi.',
    repoScanRoots: 'Iifolda eziza kukhangelwa. Shiya kungenanto ukuze kukhangelwe ifolda yakho yasekhaya.',
    repoScanExcludePaths: 'Iifolda kunye neefolda ezingaphakathi kuzo eziza kutsitywa xa kukhangelwa oovimba.',
  },
  timezone: 'Isetyenziswa xa i-OpenAmer idinga ulwazi lwexesha lendawo. Xa ingenanto, kusetyenziswa ummandla wexesha wenkqubo.',
  agent: {
    imageInputMode: 'Ilawula indlela izincamatheliso zemifanekiso ezithunyelwa ngayo kwimodeli.',
    maxTurns: 'Elona nani likhulu lamathuba okubiza izixhobo ngaphambi kokuba i-OpenAmer iyeke ukuqhuba.',
  },
  terminal: {
    cwd: 'Ifolda yeprojekthi yokungagqibekanga yomsebenzi wezixhobo nowetheminali.',
    persistentShell: 'Gcina imeko yeqokobhe phakathi kwemiyalelo xa inkonzo yangasemva ikuxhasa.',
    envPassthrough: 'Iziguquguquki zemeko-bume eziza kudluliselwa ekuqhutyweni kwezixhobo.',
    dockerImage: 'Umfanekiso wesikhongozeli osetyenziswa xa inkonzo yokuqhuba iyi-Docker.',
    singularityImage: 'Umfanekiso osetyenziswa xa inkonzo yokuqhuba iyi-Singularity.',
    modalImage: 'Umfanekiso osetyenziswa xa inkonzo yokuqhuba iyi-Modal.',
    daytonaImage: 'Umfanekiso osetyenziswa xa inkonzo yokuqhuba iyi-Daytona.',
  },
  codeExecution: { mode: 'Indlela ekuqiniswa ngayo ukuba ukuqhutywa kwekhowudi kuphelele kwiprojekthi yangoku.' },
  fileReadMaxChars: 'Elona nani likhulu loonobumba i-OpenAmer enokulifunda kwisicelo esinye sefayile.',
  approvals: {
    mode: 'Indlela i-OpenAmer ephatha ngayo imiyalelo efuna ukuvunywa ngokucacileyo.',
    timeout: 'Ixesha izicelo zokuvuma ezililindayo ngaphambi kokuphelelwa lixesha.',
  },
  security: { redactSecrets: 'Fihla iimfihlo ezifunyenweyo kumxholo obonwa yimodeli xa kunokwenzeka.' },
  checkpoints: { enabled: 'Yenza imifanekiso yokubuyisela imeko ngaphambi kokuhlela iifayile.' },
  memory: {
    memoryEnabled: 'Gcina iinkumbulo ezihlala ixesha elide ezinokunceda kwiiseshoni ezizayo.',
    userProfileEnabled: 'Gcina iprofayile emfutshane yezinto ezikhethwa ngumsebenzisi.',
  },
  context: { engine: 'Indlela yokulawula iincoko ezinde xa zisondela kumda womxholo.' },
  compression: { enabled: 'Shwankathela umxholo omdala xa iincoko ziba nkulu.' },
  voice: { autoTts: 'Thetha iimpendulo zomncedisi ngokuzenzekelayo.' },
  tts: {
    xai: {
      voiceId: 'I-ID yelizwi le-xAI (umzekelo eve) okanye i-ID yelizwi elilungiselelweyo.',
      language: 'Ikhowudi yolwimi oluthethwayo (umzekelo en, pt-BR) okanye "auto" ukuze ulwimi lufunyanwe ngokuzenzekelayo.',
      speed: 'Isantya sokudlala. 0.7 = kancinci, 1.0 = ngesiqhelo, 1.5 = ngokukhawuleza.',
      autoSpeechTags: 'Vumela i-LLM ifake iithegi zesandi ezibonisa iimvakalelo ([laughing], [sighs]) kumbhalo ngaphambi kokwenziwa kwentetho.',
      optimizeStreamingLatency: 'Ulungelelwaniso lokulibaziseka nomgangatho. 0 = owona mgangatho uphezulu, 2 = okona kulibaziseka kuncinci.',
      sampleRate: 'Iqondo lokuthatha iisampulu zesandi nge-Hz. Xa liphezulu, umgangatho uyanda neefayile ziba nkulu.',
      bitRate: 'Iqondo lamasuntswana le-MP3 nge-bps. Lisebenza kuphela xa ikhowudeki iyi-mp3.',
    },
    neutts: { device: 'Isixhobo sendawo sokuqhuba i-NeuTTS.' },
  },
  stt: {
    enabled: 'Vula ukuguqulwa kwentetho ibe ngumbhalo kwindawo okanye ngomnikezeli.',
    echoTranscripts: 'Phinda uthumele kumbhalo wencoko umbhalo wokuqala we-🎙️ wemiyalezo yelizwi.',
    elevenlabs: { languageCode: 'Ikhowudi yolwimi ye-ISO-639-3 enganyanzelekanga. Xa ingenanto, i-ElevenLabs ifumana ulwimi ngokuzenzekelayo.' },
  },
  updates: {
    nonInteractiveLocalChanges: 'Xa i-OpenAmer izihlaziya kusetyenziso ngaphandle kombuzo wetheminali, gcina utshintsho lwendawo kwikhowudi (stash) okanye ululahle (discard). Uhlaziyo lwetheminali lusoloko lubuza.',
  },
})
