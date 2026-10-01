---
id: C-2025-5052/facial-scraping-elements
document: C(2025) 5052 final
issuer: European Commission
binding: false
topic: "Art. 5(1)(e) — what a facial recognition database and untargeted scraping are, targeted
  searches and reverse image search allowed, no step-by-step circumvention, and what is out:
  other biometrics, non-AI scraping, training sets, fictitious faces, unexpanded old databases"
locator: paragraphs (226), (228), (229), (230), (231), (232), (233), (234), (235), (236), pp. 79–81
paragraphs: [226, 228, 229, 230, 231, 232, 233, 234, 235, 236]
source_url: https://ai-act-service-desk.ec.europa.eu/sites/default/files/2025-08/guidelines_on_prohibited_artificial_intelligence_practices_established_by_regulation_eu_20241689_ai_act_english_ied3r5nwo50xggpcfmwckm3nuc_112367-1.PDF
extraction: paragraphs.yaml (pdfplumber and PDFium agreeing), quoted as extracted. The
  authoritative form is the PDF at the cited page.
omits: the other paragraphs of section 6 (222 to 225, 227, 237, 238), which restate the ban, its
  purpose and conditions, define scraping generally, or point to other rules. The quoted paragraphs
  are whole; the headings that follow (226), (231) and (233) are not quoted.
retrieved_at: 2026-10-01
sha256: b9e04f9e5ad0acc43fe57c5f716f10dd08f9dc55a7cb891144ae9cb0a950f314
---

(226) The prohibition in Article 5(1)(e) AI Act covers AI systems used to create or expand facial recognition databases. ‘Database’ in this context should be understood to refer to any collection of data, or information, that is specially organized for rapid search and retrieval by a computer. A facial recognition database is capable of matching a human face from a digital image or video frame against a database of faces, comparing it to images in the database and determining whether there is a likely match between the two. Such a facial recognition database may be temporary, centralised or decentralised. Article 5(1)(e) does not require that the sole purpose of the database is to be used for facial recognition; it is sufficient that the database can be used for facial recognition. […]

(228) ‘Untargeted’ relates to a technique that operates like a ‘vacuum cleaner’, absorbing as much data and information as possible, without targeting specifically and individually intended subject(s) of the scarping. Scraping indiscriminately harvests data or content. Thus, the notion of ‘untargeted’ means without a specific focus on a given individual or group of individuals. The respect of opt-out of internet protocols such as robot.txt does not affect the untargeted nature of the scraping.

(229) If a scraping tool is instructed to collect images or video containing human faces only of specific individuals or a pre-defined group of persons, then the scraping becomes targeted, for example to find one specific criminal or to identify a group of victims. Such scraping is not covered by the prohibition in Article 5(1)(e) AI Act.

(230) For example, the targeted collection of images focusing on a class of victims, by using crawlers to pick up on images of victims that human traffickers post/advertise on social media channels, is not covered by the prohibition. Untargeted scraping should be interpreted in a manner that does not allow circumvention of the prohibition. The scraping of the Internet or CCTV footage for the creation of a database step-by-step, thereby selecting specific groups of individuals or other criteria each time, should fall within the prohibition of Article 5(1)(e) AI Act where the end-result is functionally the same as pursuing untargeted scraping from the outset.

(231) Where systems combine targeted searches for images or videos with untargeted searches, the untargeted scraping is prohibited. […]

(232) For the prohibition in Article 5(1)(e) AI Act to apply, the source of the facial images may either be the Internet or CCTV footage. Regarding the internet, the fact that a person has published facial images of themselves on a social media platform does not mean that that person has given his or her consent for those images to be included in a facial recognition database. Examples of scraping facial images from CCTV footage include images acquired by surveillance cameras operated in places such as airports, streets, parks, etc. Example: A facial recognition software company collects pictures of faces. The photographs held by the company have been scraped from social media (e.g., Facebook, YouTube, Twitter, Venmo) with an ‘automated image scraper’ that searches the internet and detects images containing human faces. It collects those images with any associated information (such as the source of the image (URL), the geo-localisation, and sometimes the names of the individuals). The facial features are then extracted from the images and transformed into mathematical representations, which are hashed for indexation and future comparison. When a user uploads the image of an individual to the AI system, that system will determine whether that image matches a face in the database. The uploaded image will go through the same mathematical transformation as the scraped images.

(233) Where an AI system receives a picture of a person and searches the face on the internet for matches, i.e. ‘reverse engineering image search engines’, this will be considered to be targeted scraping. Moreover, it is questionable whether the matches would appear in a ‘database’. […]

(234) The prohibition in Article 5(1)(e) AI Act does not apply to the untargeted scraping of biometric data other than facial images (such as voice samples). The prohibition does also not apply where no AI systems are involved in the scraping. Facial image databases that are not used for the recognition of persons are also out of scope, such as facial image databases used for AI model training or testing purposes, where the persons are not identified.

(235) The prohibition in Article 5(1)(e) AI Act does not apply to AI systems which harvest large amounts of facial images from the internet to build AI models that generate new images about fictitious persons because such systems would not result in the recognition of real persons. Such AI systems could fall under the transparency requirements of Article 50 AI Act.

(236) The prohibition in Article 5(1)(e) AI Act covers AI systems used to create or expand facial recognition databases. When it comes to existing facial databases built up prior to the entry into application of the prohibition, which are not further expanded through AI-enabled untargeted scraping, those databases and their use must comply with the applicable Union data protection rules.
