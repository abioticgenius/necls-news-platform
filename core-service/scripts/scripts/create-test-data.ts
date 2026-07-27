import 'dotenv/config';
import { v4 as uuidv4 } from 'uuid';
import { Event } from '../src/db/app-db/models/event.model';
import { Category } from '../src/db/app-db/models/category.model';
import { Source } from '../src/db/app-db/models/source.model';
import { Language } from '../src/db/app-db/models/language.model';
import { LocalizedEventData } from '../src/db/app-db/models/localizedeventdata.model';
import { EventSoFar } from '../src/db/app-db/models/eventsofar.model';
import { EventAnalysis } from '../src/db/app-db/models/eventanalysis.model';
import { LocalizedEventSoFar } from '../src/db/app-db/models/localizedeventsofar.model';
import { LocalizedEventAnalysis } from '../src/db/app-db/models/localizedeventanalysis.model';
import { initAppDb } from '../src/db/app-db';
import { SeoTag } from '../src/db/app-db/models/seotag.model';
import { EventSeoTag } from '../src/db/app-db/models/eventseotag.model';
import { Logos } from '../src/db/app-db/models/logos.model';
import { Collection } from '../src/db/app-db/models/collection.model';
// Sample data
const categories = [
  { name: 'Sports' },
  { name: 'Business' },
  { name: 'Environment' },
  { name: 'Entertainment' },
  { name: 'Society' }
];

export const sampleCategoryTags = [
  { name: 'Sports', type: 'category' },
  { name: 'Business', type: 'category' },
  { name: 'Environment', type: 'category' },
  { name: 'Entertainment', type: 'category' },
  { name: 'Society', type: 'category' }
];

export const sampleTags = [
  { name: 'Politics', type: 'tag' },
  { name: 'Technology', type: 'tag' },
  { name: 'World', type: 'tag' },
  { name: 'Health', type: 'tag' },
  { name: 'Science', type: 'tag' },
];
const languages = [
  { id: 'en', name: 'English' },
  { id: 'hi', name: 'Hindi' }
];

// Sample image URLs from Unsplash (free to use)
const sampleImages = [
  'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=800', // Business
  'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=800', // Sports
  'https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=800', // Environment
  'https://images.unsplash.com/photo-1489599904983-8de9dc465386?w=800', // Entertainment
  'https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=800', // Society
  'https://images.unsplash.com/photo-1586339949916-3e9457bef6d3?w=800', // Business
  'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800', // Sports
  'https://images.unsplash.com/photo-1542601906990-b4d3fb778b09?w=800', // Environment
  'https://images.unsplash.com/photo-1518676590629-3dcbd9c5a5c9?w=800', // Entertainment
  'https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?w=800'  // Society
];

// Sample audio URLs (placeholder - you can replace with actual audio URLs)
const sampleAudios = [
  'necls-backend-adhoc/audio/032c64dc-0776-57cf-8f92-5aeaad16223a_en.wav',
  'necls-backend-adhoc/audio/0465b6a1-718a-52be-a15f-5fde9f370b02_en.wav',
  'necls-backend-adhoc/audio/017eb7de-3013-5180-aaf5-5722cfc4d0d8_en.wav',
  'necls-backend-adhoc/audio/063be9f4-9c41-5b24-99ce-12514f8e8e23_en.wav',
  'necls-backend-adhoc/audio/0682d844-9e87-5478-83ae-7af23dbb6c26_en.wav'
];

const sampleAudiosHindi = [
  'necls-backend-adhoc/audio/0465b6a1-718a-52be-a15f-5fde9f370b02_hi.wav',
  'necls-backend-adhoc/audio/0682d844-9e87-5478-83ae-7af23dbb6c26_hi.wav',
  'necls-backend-adhoc/audio/063be9f4-9c41-5b24-99ce-12514f8e8e23_hi.wav',
  'necls-backend-adhoc/audio/0778df78-218c-5014-aca2-6a699fb43f35_hi.wav',
  'necls-backend-adhoc/audio/089d1c4b-7ca8-5178-a3ec-e3827684f455_hi.wav'
];

// Sample news sources
const newsSources = [
  { title: 'Global News Network', logo: 'https://via.placeholder.com/100x50/0066cc/ffffff?text=GNN' },
  { title: 'World Sports Today', logo: 'https://via.placeholder.com/100x50/ff6600/ffffff?text=WST' },
  { title: 'Business Weekly', logo: 'https://via.placeholder.com/100x50/009900/ffffff?text=BW' },
  { title: 'Entertainment Express', logo: 'https://via.placeholder.com/100x50/cc0066/ffffff?text=EE' },
  { title: 'Environment Watch', logo: 'https://via.placeholder.com/100x50/669900/ffffff?text=EW' },
  { title: 'Society Times', logo: 'https://via.placeholder.com/100x50/9900cc/ffffff?text=ST' },
  { title: 'Daily Herald', logo: 'https://via.placeholder.com/100x50/ff3300/ffffff?text=DH' },
  { title: 'Tech Tribune', logo: 'https://via.placeholder.com/100x50/0099cc/ffffff?text=TT' }
];

// Sample article templates by category
const articleTemplates = {
  Sports: {
    en: {
      titles: [
        'Championship Final Draws Record Crowd',
        'Star Player Signs Historic Contract',
        'Olympic Preparations Underway',
        'Local Team Advances to Playoffs',
        'New Stadium Opens to Fanfare',
        'Record-Breaking Performance Stuns Audience',
        'International Tournament Begins',
        'Veteran Coach Announces Retirement',
        'Youth League Shows Promise',
        'Sports Technology Revolutionizes Training'
      ],
      descriptions: [
        'Fans gather in unprecedented numbers for the most anticipated sporting event of the year.',
        'A groundbreaking deal reshapes the landscape of professional sports.',
        'Athletes prepare for the upcoming international competition with intensive training.',
        'The underdog team defies expectations with their remarkable performance.',
        'State-of-the-art facility promises to enhance the fan experience.',
        'A new record is set that may stand for years to come.',
        'Teams from around the world compete for the prestigious title.',
        'A legendary figure in sports bids farewell to an illustrious career.',
        'Young athletes demonstrate exceptional skill and potential.',
        'Innovation in sports science opens new possibilities for performance.'
      ]
    },
    hi: {
      titles: [
        'चैंपियनशिप फाइनल में रिकॉर्ड भीड़',
        'स्टार खिलाड़ी ने ऐतिहासिक अनुबंध पर हस्ताक्षर किए',
        'ओलंपिक तैयारियां जारी',
        'स्थानीय टीम प्लेऑफ में आगे बढ़ी',
        'नया स्टेडियम धूमधाम से खुला',
        'रिकॉर्ड तोड़ प्रदर्शन ने दर्शकों को चौंका दिया',
        'अंतर्राष्ट्रीय टूर्नामेंट शुरू',
        'अनुभवी कोच ने सेवानिवृत्ति की घोषणा की',
        'युवा लीग में दिखी उम्मीद',
        'खेल तकनीक ने प्रशिक्षण में क्रांति ला दी'
      ],
      descriptions: [
        'साल के सबसे प्रतीक्षित खेल आयोजन के लिए प्रशंसक अभूतपूर्व संख्या में एकत्रित हुए।',
        'एक अभूतपूर्व समझौते ने पेशेवर खेलों के परिदृश्य को नया आकार दिया।',
        'एथलीट गहन प्रशिक्षण के साथ आगामी अंतर्राष्ट्रीय प्रतियोगिता की तैयारी कर रहे हैं।',
        'कमजोर टीम ने अपने उल्लेखनीय प्रदर्शन से अपेक्षाओं को धता बताया।',
        'अत्याधुनिक सुविधा प्रशंसकों के अनुभव को बेहतर बनाने का वादा करती है।',
        'एक नया रिकॉर्ड स्थापित किया गया जो वर्षों तक बना रह सकता है।',
        'दुनिया भर की टीमें प्रतिष्ठित खिताब के लिए प्रतिस्पर्धा कर रही हैं।',
        'खेल जगत की एक महान हस्ती ने अपने शानदार करियर को अलविदा कहा।',
        'युवा एथलीटों ने असाधारण कौशल और क्षमता का प्रदर्शन किया।',
        'खेल विज्ञान में नवाचार ने प्रदर्शन के लिए नई संभावनाएं खोली हैं।'
      ]
    }
  },
  Business: {
    en: {
      titles: [
        'Tech Giant Reports Record Quarterly Earnings',
        'Startup Secures Major Investment Round',
        'Global Supply Chain Faces New Challenges',
        'Cryptocurrency Market Shows Volatility',
        'Green Energy Investments Surge',
        'Retail Sector Adapts to Digital Transformation',
        'Banking Industry Embraces AI Technology',
        'Small Business Support Programs Launched',
        'International Trade Agreement Signed',
        'Economic Recovery Shows Positive Signs'
      ],
      descriptions: [
        'Technology company exceeds analyst expectations with impressive financial results.',
        'Emerging company attracts significant funding from venture capital firms.',
        'International shipping and logistics face unprecedented obstacles.',
        'Digital currencies experience significant price fluctuations in global markets.',
        'Renewable energy sector attracts substantial investor interest and capital.',
        'Traditional retailers innovate to compete in the digital marketplace.',
        'Financial institutions leverage artificial intelligence for improved services.',
        'Government initiatives aim to assist entrepreneurs and small enterprises.',
        'Nations reach consensus on important economic cooperation framework.',
        'Key indicators suggest improving economic conditions and growth prospects.'
      ]
    },
    hi: {
      titles: [
        'तकनीकी कंपनी ने नया निवेश दौर पूरा किया',
        'स्टार्टअप ने अंतर्राष्ट्रीय बाजार में प्रवेश किया',
        'निर्माण क्षेत्र में डिजिटल परिवर्तन',
        'व्यापार नेता ने नई पहल की घोषणा की',
        'आर्थिक संकेतक सकारात्मक वृद्धि दिखाते हैं',
        'स्थानीय उद्यमी को प्रतिष्ठित पुरस्कार मिला',
        'कंपनी विलय से बाजार हिस्सेदारी बढ़ाएगी',
        'हरित प्रौद्योगिकी में नया निवेश',
        'ई-कॉमर्स ट्रेंड्स उपभोक्ता व्यवहार बदल रहे हैं',
        'कॉर्पोरेट साझेदारी नवाचार को बढ़ावा देती है'
      ],
      descriptions: [
        'एक नवाचार आधारित उद्यम ने महत्वपूर्ण विकास के लिए वित्तपोषण प्राप्त किया।',
        'एक उभरती कंपनी ने सीमाओं के पार अपने संचालन का विस्तार करने में सफलता पाई।',
        'उद्योग अत्याधुनिक तकनीक अपनाकर आधुनिकीकरण कर रहा है।',
        'एक प्रभावशाली व्यापारिक व्यक्तित्व ने एक दूरदर्शी परियोजना का अनावरण किया।',
        'बाजार डेटा आर्थिक वसूली और विस्तार के संकेत दिखाता है।',
        'एक स्थानीय नवप्रवर्तक को उनकी उत्कृष्टता के लिए सम्मानित किया गया।',
        'रणनीतिक गठबंधन से प्रतिस्पर्धी बढ़त हासिल होने की उम्मीद।',
        'पर्यावरण-अनुकूल समाधान निवेशकों का ध्यान आकर्षित कर रहे हैं।',
        'डिजिटल खरीदारी पैटर्न पारंपरिक रिटेल को फिर से परिभाषित कर रहे हैं।',
        'सहयोगी उद्यम क्षेत्र में तकनीकी प्रगति को तेज कर रहे हैं।'
      ]
    }
  },
  Environment: {
    en: {
      titles: [
        'Climate Summit Reaches Historic Agreement',
        'Renewable Energy Adoption Accelerates',
        'Ocean Cleanup Initiative Shows Progress',
        'Forest Conservation Efforts Expand',
        'Wildlife Protection Program Launches',
        'Sustainable Agriculture Practices Grow',
        'Air Quality Improvements Measured',
        'Recycling Technology Advances',
        'Green Transportation Solutions Emerge',
        'Carbon Emission Reduction Targets Met'
      ],
      descriptions: [
        'World leaders unite on comprehensive environmental protection measures.',
        'Solar and wind power installations reach new milestone numbers.',
        'Innovative technology removes plastic waste from marine ecosystems.',
        'International cooperation preserves vital forest habitats.',
        'New measures protect endangered species and their natural environments.',
        'Farmers adopt eco-friendly methods that benefit soil and water.',
        'Urban areas report cleaner air due to pollution reduction efforts.',
        'Advanced recycling processes transform waste into valuable resources.',
        'Electric vehicles and clean public transit options expand rapidly.',
        'Nations successfully reduce greenhouse gas emissions ahead of schedule.'
      ]
    },
    hi: {
      titles: [
        'नवीकरणीय ऊर्जा परियोजना ने मील का पत्थर हासिल किया',
        'शहरी क्षेत्र में हरित स्थान की पहल शुरू',
        'समुदाय ने स्थानीय वन्यजीव संरक्षण का समर्थन किया',
        'जलवायु अनुकूलन उपाय लागू किए गए',
        'पुनर्चक्रण कार्यक्रम प्रभावशाली परिणाम दिखाता है',
        'समुद्री संरक्षण प्रयास सफल साबित हुए',
        'स्थायी कृषि प्रथाएं फैल रही हैं',
        'कार्बन न्यूट्रल लक्ष्य निर्धारित किए गए',
        'पर्यावरण शिक्षा कार्यक्रम लॉन्च',
        'इको-फ्रेंडली आवास प्रोजेक्ट में रुचि बढ़ी'
      ],
      descriptions: [
        'स्वच्छ ऊर्जा विकास में एक महत्वपूर्ण उपलब्धि हासिल की गई।',
        'शहरी योजनाकर्ता पर्यावरणीय रूप से टिकाऊ विकास को प्राथमिकता दे रहे हैं।',
        'स्थानीय निवासी प्राकृतिक पारिस्थितिकी तंत्र की सुरक्षा में सक्रिय भूमिका निभा रहे हैं।',
        'पर्यावरणीय चुनौतियों से निपटने के लिए अभिनव समाधान लागू किए जा रहे हैं।',
        'कचरा प्रबंधन नवाचार समुदायिक सहभागिता को प्रेरित कर रहे हैं।',
        'समुद्री पारिस्थितिकी तंत्र संरक्षण प्रयास सकारात्मक परिणाम दे रहे हैं।',
        'किसान पर्यावरण-अनुकूल खेती की तकनीकें अपना रहे हैं।',
        'संगठन अपने पर्यावरणीय प्रभाव को कम करने के लिए प्रतिबद्ध हैं।',
        'नई शैक्षणिक पहल पर्यावरण जागरूकता बढ़ा रही है।',
        'टिकाऊ निर्माण समाधान मुख्यधारा में स्वीकार्यता पा रहे हैं।'
      ]
    }
  },
  Entertainment: {
    en: {
      titles: [
        'Film Festival Showcases Independent Cinema',
        'Music Artist Announces World Tour',
        'Streaming Platform Launches Original Series',
        'Theater Production Receives Standing Ovation',
        'Video Game Industry Sets Revenue Record',
        'Celebrity Chef Opens New Restaurant',
        'Art Exhibition Draws International Attention',
        'Comedy Special Breaks Viewership Records',
        'Fashion Week Highlights Sustainable Design',
        'Books Sales Surge for Debut Novelist'
      ],
      descriptions: [
        'Emerging filmmakers present innovative stories at prestigious annual event.',
        'Popular musician plans extensive concert series across multiple continents.',
        'New exclusive content premieres on major streaming service.',
        'Broadway-style show receives overwhelming audience appreciation.',
        'Gaming companies report unprecedented financial success.',
        'Renowned culinary expert expands restaurant empire with new venture.',
        'Contemporary art display attracts visitors from around the globe.',
        'Stand-up performance achieves record-breaking audience engagement.',
        'Fashion designers emphasize environmental responsibility in latest collections.',
        'First-time author achieves remarkable commercial and critical success.'
      ]
    },
    hi: {
      titles: [
        'फिल्म फेस्टिवल में नई प्रतिभा का जश्न',
        'संगीत कार्यक्रम ने दर्शकों को मंत्रमुग्ध किया',
        'टीवी सीरीज ने रिकॉर्ड व्यूअरशिप हासिल की',
        'कलाकार ने प्रतिष्ठित पुरस्कार जीता',
        'ब्रॉडवे शो के लिए बुकिंग तेजी से बढ़ी',
        'डिजिटल स्ट्रीमिंग प्लेटफॉर्म ने नई सामग्री लॉन्च की',
        'सेलिब्रिटी ने धर्मार्थ कारण का समर्थन किया',
        'फैशन वीक ने वैश्विक ध्यान आकर्षित किया',
        'गेमिंग टूर्नामेंट ने नए रिकॉर्ड बनाए',
        'पॉडकास्ट श्रृंखला ने लोकप्रियता हासिल की'
      ],
      descriptions: [
        'उभरते फिल्म निर्माता अपनी कलात्मक दृष्टि के लिए पहचान पा रहे हैं।',
        'संगीत प्रदर्शन ने दर्शकों पर गहरा प्रभाव छोड़ा।',
        'ड्रामा सीरीज ने अपेक्षाओं को पार करके व्यापक दर्शक आधार हासिल किया।',
        'मनोरंजन उद्योग में उत्कृष्टता को सम्मानित किया गया।',
        'रंगमंच निर्माण में असाधारण रुचि दिखाई गई।',
        'नई मीडिया सामग्री विविध ऑडियंस आवश्यकताओं को पूरा कर रही है।',
        'एक प्रसिद्ध व्यक्तित्व ने सामाजिक कारणों के लिए अपना मंच उपयोग किया।',
        'फैशन इवेंट ने रचनात्मकता और शैली के नए मानक स्थापित किए।',
        'वीडियो गेम प्रतियोगिता ने ई-स्पोर्ट्स की बढ़ती लोकप्रियता को दर्शाया।',
        'ऑडियो कंटेंट ने नए कहानी सुनाने के तरीकों को प्रभावी बनाया।'
      ]
    }
  },
  Society: {
    en: {
      titles: [
        'Community Center Opens in Underserved Neighborhood',
        'Volunteer Program Exceeds Participation Goals',
        'Education Initiative Shows Promising Results',
        'Healthcare Access Improves in Rural Areas',
        'Cultural Festival Celebrates Diversity',
        'Social Housing Project Breaks Ground',
        'Mental Health Awareness Campaign Launches',
        'Senior Citizens Program Expands Services',
        'Youth Mentorship Initiative Grows',
        'Public Safety Measures Enhance Community Security'
      ],
      descriptions: [
        'New facility provides essential services and programs for local residents.',
        'Community volunteers demonstrate exceptional commitment to social causes.',
        'Educational reforms show measurable improvements in student outcomes.',
        'Medical services become more accessible to remote and rural populations.',
        'Annual celebration highlights the rich cultural heritage of diverse communities.',
        'Affordable housing development addresses critical accommodation shortage.',
        'Public awareness efforts focus on mental health support and resources.',
        'Expanded programs offer enhanced quality of life for elderly residents.',
        'Young people benefit from guidance and support of experienced mentors.',
        'Enhanced security measures create safer environment for all community members.'
      ]
    },
    hi: {
      titles: [
        'शिक्षा प्रणाली में सुधार की पहल शुरू',
        'स्वास्थ्य सेवा पहुंच में वृद्धि',
        'सामुदायिक केंद्र का उद्घाटन समारोह',
        'डिजिटल साक्षरता कार्यक्रम का विस्तार',
        'सामाजिक न्याय अभियान में गति',
        'वरिष्ठ नागरिक सेवाओं में सुधार',
        'सार्वजनिक परिवहन का आधुनिकीकरण',
        'युवा सशक्तिकरण परियोजना शुरू',
        'मानसिक स्वास्थ्य जागरूकता अभियान',
        'विकलांग अधिकार वकालत में प्रगति'
      ],
      descriptions: [
        'नई नीतियां छात्रों के लिए बेहतर शैक्षणिक अवसर बनाने का लक्ष्य रखती हैं।',
        'नई सुविधाएं अधिक निवासियों को चिकित्सा सेवा प्रदान करने में मदद करेंगी।',
        'समुदाय के सदस्य स्थानीय गतिविधियों और कार्यक्रमों के लिए नया स्थान मनाते हैं।',
        'प्रौद्योगिकी कौशल प्रशिक्षण अधिक आबादी तक पहुंच रहा है।',
        'न्यायसंगत व्यवहार और समान अवसरों के लिए आंदोलन गति पकड़ रहा है।',
        'बुजुर्ग नागरिकों की जरूरतों को पूरा करने के लिए संसाधन बढ़ाए जा रहे हैं।',
        'बेहतर कनेक्टिविटी समुदाय के सदस्यों को अधिक गतिशीलता प्रदान करती है।',
        'युवाओं को अपने लक्ष्य हासिल करने के लिए समर्थन और अवसर दिए जा रहे हैं।',
        'मानसिक कल्याण संसाधन और समर्थन को अधिक दृश्यमान बनाया जा रहा है।',
        'समावेशी वातावरण बनाने और बाधाओं को दूर करने की दिशा में प्रगति हो रही है।'
      ]
    }
  }
};

// Content types for variety
const contentTypes = ['bullets', 'text', 'table', 'timeline', 'stakeholder_impact'];

// Sample content for different types
const sampleContent = {
  bullets: {
    en: [
      "Key stakeholders express optimism about future developments",
      "Economic indicators show positive trends across multiple sectors",
      "International cooperation continues to strengthen relationships",
      "Technology adoption accelerates in various industries",
      "Community engagement reaches new participation levels"
    ],
    hi: [
      "मुख्य हितधारक भविष्य के विकास के बारे में आशावाद व्यक्त करते हैं",
      "आर्थिक संकेतक कई क्षेत्रों में सकारात्मक रुझान दिखाते हैं",
      "अंतर्राष्ट्रीय सहयोग संबंधों को मजबूत बनाना जारी रखता है",
      "विभिन्न उद्योगों में प्रौद्योगिकी अपनाने की गति तेज हो रही है",
      "सामुदायिक भागीदारी नए स्तर पर पहुंच गई है"
    ]
  },
  text: {
    en: "This development represents a significant milestone in addressing long-standing challenges. The comprehensive approach involves multiple stakeholders working together to create sustainable solutions that benefit the entire community. Early indicators suggest that the initiative is gaining momentum and support from various sectors.",
    hi: "यह विकास लंबे समय से चली आ रही चुनौतियों से निपटने में एक महत्वपूर्ण मील का पत्थर है। व्यापक दृष्टिकोण में कई हितधारक मिलकर टिकाऊ समाधान बनाने के लिए काम कर रहे हैं जो पूरे समुदाय को लाभ पहुंचाते हैं। प्रारंभिक संकेतक बताते हैं कि इस पहल को विभिन्न क्षेत्रों से गति और समर्थन मिल रहा है।"
  },
  timeline: {
    en: [
      {
        date: "2024-01-15",
        content: "Initial planning and stakeholder consultation phase begins"
      },
      {
        date: "2024-03-20",
        content: "Project approval received from regulatory authorities"
      },
      {
        date: "2024-06-10",
        content: "Implementation phase commences with community engagement"
      },
      {
        date: "2024-09-05",
        content: "First milestone achieved with significant progress reported"
      }
    ],
    hi: [
      {
        date: "2024-01-15",
        content: "प्रारंभिक योजना और हितधारक परामर्श चरण शुरू"
      },
      {
        date: "2024-03-20",
        content: "नियामक अधिकारियों से परियोजना अनुमोदन प्राप्त"
      },
      {
        date: "2024-06-10",
        content: "सामुदायिक सहभागिता के साथ कार्यान्वयन चरण शुरू"
      },
      {
        date: "2024-09-05",
        content: "महत्वपूर्ण प्रगति के साथ पहला मील का पत्थर हासिल"
      }
    ]
  },
  table: {
    en: [
      {
        title: "Financial Impact",
        data: {
          "Investment": "$2.5 Million",
          "Expected ROI": "15-20%",
          "Timeline": "24 months",
          "Risk Level": "Medium"
        }
      },
      {
        title: "Resource Allocation",
        data: {
          "Human Resources": "25 specialists",
          "Technology": "Cloud infrastructure",
          "Equipment": "Modern tools and systems",
          "Training": "Comprehensive program"
        }
      }
    ],
    hi: [
      {
        title: "वित्तीय प्रभाव",
        data: {
          "निवेश": "2.5 मिलियन डॉलर",
          "अपेक्षित रिटर्न": "15-20%",
          "समयसीमा": "24 महीने",
          "जोखिम स्तर": "मध्यम"
        }
      },
      {
        title: "संसाधन आवंटन",
        data: {
          "मानव संसाधन": "25 विशेषज्ञ",
          "प्रौद्योगिकी": "क्लाउड अवसंरचना",
          "उपकरण": "आधुनिक उपकरण और सिस्टम",
          "प्रशिक्षण": "व्यापक कार्यक्रम"
        }
      }
    ]
  },
  stakeholderImpact: {
    en: [
      {
        title: "Local Communities",
        description: "Enhanced services and improved quality of life",
        impact: "positive"
      },
      {
        title: "Business Sector",
        description: "New opportunities for growth and investment",
        impact: "positive"
      },
      {
        title: "Government",
        description: "Increased administrative responsibilities",
        impact: "negative"
      },
      {
        title: "Environmental Groups",
        description: "Mixed outcomes with both benefits and concerns",
        impact: "neutral"
      }
    ],
    hi: [
      {
        title: "स्थानीय समुदाय",
        description: "बेहतर सेवाएं और जीवन की गुणवत्ता में सुधार",
        impact: "positive"
      },
      {
        title: "व्यापारिक क्षेत्र",
        description: "विकास और निवेश के नए अवसर",
        impact: "positive"
      },
      {
        title: "सरकार",
        description: "प्रशासनिक जिम्मेदारियों में वृद्धि",
        impact: "negative"
      },
      {
        title: "पर्यावरण समूह",
        description: "लाभ और चिंताओं दोनों के साथ मिश्रित परिणाम",
        impact: "neutral"
      }
    ]
  }
};

function getRandomElement<T>(array: T[]): T {
  return array[Math.floor(Math.random() * array.length)];
}

function getRandomDate(start: Date, end: Date): Date {
  return new Date(start.getTime() + Math.random() * (end.getTime() - start.getTime()));
}

function generateRandomUrl(): string {
  const domains = ['example.com', 'news-source.org', 'media-outlet.net', 'press-agency.com'];
  const paths = ['news', 'articles', 'reports', 'stories'];
  const domain = getRandomElement(domains);
  const path = getRandomElement(paths);
  const id = Math.random().toString(36).substr(2, 9);
  return `https://${domain}/${path}/${id}`;
}

async function createTestData() {
  try {
    console.log('Initializing database...');
    await initAppDb();

    console.log('Creating categories...');
    const createdCategories = await Promise.all(
      categories.map(category =>
        Category.findOrCreate({
          where: { name: category.name },
          defaults: {
            id: uuidv4(),
            name: category.name
          }
        }).then(([instance]) => instance)
      )
    );

    console.log('Created categories:', createdCategories.map(c => ({ id: c.id, name: c.name })));

    console.log('Creating tags...');
    const createdCategoryTags = await Promise.all(
      sampleCategoryTags.map(tag =>
        SeoTag.findOrCreate({
          where: { name: tag.name, type: tag.type },
          defaults: {
            id: uuidv4(),
            name: tag.name,
            type: tag.type
          }
        }).then(([instance]) => instance)
      )
    );
    const createdTags = await Promise.all(
      sampleTags.map(tag =>
        SeoTag.findOrCreate({
          where: { name: tag.name, type: tag.type },
          defaults: {
            id: uuidv4(),
            name: tag.name,
            type: tag.type
          }
        }).then(([instance]) => instance)
      )
    );
    console.log('Created tags:', createdCategoryTags.map(c => ({ id: c.id, name: c.name })));
    console.log('Created tags:', createdTags.map(c => ({ id: c.id, name: c.name })));

    console.log('Creating/updating languages...');
    for (const lang of languages) {
      await Language.findOrCreate({
        where: { id: lang.id },
        defaults: { id: lang.id, name: lang.name }
      });
    }

    console.log('Creating 1000 news articles...');
    const startDate = new Date('2024-01-01');
    const endDate = new Date('2025-12-31');
    let collection;
    for (let i = 0; i < 1000; i++) {
      const category = getRandomElement(createdCategories);
      console.log(`Creating article ${i + 1}, category:`, category.name, 'id:', category.id);
      const categoryName = category.name as keyof typeof articleTemplates;
      const templates = articleTemplates[categoryName];

      // Create event
      const eventId = uuidv4();
      const predictionId = uuidv4();
      const createdDate = getRandomDate(startDate, endDate);
      const timeStamp = getRandomDate(createdDate, endDate);

      const event = await Event.create({
        id: eventId,
        image: getRandomElement(sampleImages),
        category_id: category.id,
        time_stamp: timeStamp,
        created_date: createdDate
      });
      // create category tag
      const tag = await EventSeoTag.create({
        event_id: eventId,
        seo_tag_id: getRandomElement(createdCategoryTags).id
      });
      if (!collection) {
        collection = {
          title: 'Business',
          description: 'Business World',
          tags: [tag.id]
        };
        await Collection.create(collection)
      }

      const tags = createdTags.sort(() => Math.random() - 0.5).slice(0, 3)
      for (const t of tags) {
        await EventSeoTag.create({
          event_id: eventId,
          seo_tag_id: t.id,
        });
      }

      // Create source
      const sourceData = getRandomElement(newsSources);
      const logo = await Logos.create({
        id: uuidv4(),
        name: sourceData.title,
        url: sourceData.logo,
        website: generateRandomUrl()
      });

      await Source.create({
        id: uuidv4(),
        title: sourceData.title,
        event_id: eventId,
        source_url: generateRandomUrl(),
        logo_id: logo.id
      });

      // Create localized event data for both languages
      for (const lang of languages) {
        const isEnglish = lang.id === 'en';
        const langTemplates = isEnglish ? templates.en : templates.hi;
        const contentType = getRandomElement(contentTypes) as any;

        let content;
        if (contentType === 'bullets') {
          content = isEnglish ? sampleContent.bullets.en : sampleContent.bullets.hi;
        } else if (contentType === 'stakeholder_impact') {
          content = isEnglish ? sampleContent.stakeholderImpact.en : sampleContent.stakeholderImpact.hi;
        } else if (contentType === 'timeline') {
          content = isEnglish ? sampleContent.timeline.en : sampleContent.timeline.hi;
        } else if (contentType === 'table') {
          content = isEnglish ? sampleContent.table.en : sampleContent.table.hi;
        } else {
          content = isEnglish ? sampleContent.text.en : sampleContent.text.hi;
        }

        await LocalizedEventData.create({
          id: uuidv4(),
          language_id: lang.id,
          event_id: eventId,
          title: getRandomElement(langTemplates.titles),
          description: getRandomElement(langTemplates.descriptions),
          content: content,
          contentType: contentType,
          audio: getRandomElement(lang.id === 'en' ? sampleAudios : sampleAudiosHindi)
        });
      }

      // Create some past events (story so far)
      const numPastEvents = Math.floor(Math.random() * 3) + 1; // 1-3 past events
      for (let j = 0; j < numPastEvents; j++) {
        const pastEventId = uuidv4();
        await EventSoFar.create({
          id: pastEventId,
          event_id: eventId,
          sequence: j + 1
        });

        // Create localized past data
        for (const lang of languages) {
          const isEnglish = lang.id === 'en';
          const contentType = getRandomElement(contentTypes) as any;

          let content;
          if (contentType === 'bullets') {
            content = isEnglish ? sampleContent.bullets.en : sampleContent.bullets.hi;
          } else if (contentType === 'stakeholder_impact') {
            content = isEnglish ? sampleContent.stakeholderImpact.en : sampleContent.stakeholderImpact.hi;
          } else if (contentType === 'timeline') {
            content = isEnglish ? sampleContent.timeline.en : sampleContent.timeline.hi;
          } else if (contentType === 'table') {
            content = isEnglish ? sampleContent.table.en : sampleContent.table.hi;
          } else {
            content = isEnglish ? sampleContent.text.en : sampleContent.text.hi;
          }

          await LocalizedEventSoFar.create({
            id: uuidv4(),
            language_id: lang.id,
            event_so_far_id: pastEventId,
            content: content,
            contentType: contentType
          });
        }
      }

      // Create some prediction events (what's next)
      const numPredictions = Math.floor(Math.random() * 3) + 1; // 1-3 predictions
      for (let k = 0; k < numPredictions; k++) {
        const predictionEventId = uuidv4();
        await EventAnalysis.create({
          id: predictionEventId,
          event_id: eventId,
          sequence: k + 1
        });

        // Create localized prediction data
        for (const lang of languages) {
          const isEnglish = lang.id === 'en';
          const contentType = getRandomElement(contentTypes) as any;

          let content;
          if (contentType === 'bullets') {
            content = isEnglish ? sampleContent.bullets.en : sampleContent.bullets.hi;
          } else if (contentType === 'stakeholder_impact') {
            content = isEnglish ? sampleContent.stakeholderImpact.en : sampleContent.stakeholderImpact.hi;
          } else if (contentType === 'timeline') {
            content = isEnglish ? sampleContent.timeline.en : sampleContent.timeline.hi;
          } else if (contentType === 'table') {
            content = isEnglish ? sampleContent.table.en : sampleContent.table.hi;
          } else {
            content = isEnglish ? sampleContent.text.en : sampleContent.text.hi;
          }

          await LocalizedEventAnalysis.create({
            id: uuidv4(),
            language_id: lang.id,
            event_analysis_id: predictionEventId,
            content: content,
            contentType: contentType
          });
        }
      }

      // Progress indicator
      if ((i + 1) % 100 === 0) {
        console.log(`Created ${i + 1} articles...`);
      }
    }

    console.log('✅ Successfully created 1000 news articles with:');
    console.log('   - 5 categories: Sports, Business, Environment, Entertainment, Society');
    console.log('   - 2 languages: English and Hindi');
    console.log('   - Random images from Unsplash');
    console.log('   - Sample audio files');
    console.log('   - Multiple sources');
    console.log('   - Story so far (past events)');
    console.log('   - What\'s next (predictions)');
    console.log('   - Various content types (bullets, text, stakeholder impact)');

  } catch (error) {
    console.error('❌ Error creating test data:', error);
    throw error;
  }
}

// Run the script
createTestData()
  .then(() => {
    console.log('🎉 Test data creation completed successfully!');
    process.exit(0);
  })
  .catch((error) => {
    console.error('💥 Test data creation failed:', error);
    process.exit(1);
  });
