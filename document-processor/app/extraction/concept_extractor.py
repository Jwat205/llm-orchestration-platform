"""
Concept extractor for identifying abstract concepts, themes, and topics in documents
"""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict, Counter
from dataclasses import dataclass
from enum import Enum
import math

# NLP libraries (with fallbacks)
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import KMeans, DBSCAN
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

logger = logging.getLogger(__name__)


class ConceptType(Enum):
    """Types of concepts that can be extracted"""
    THEME = "THEME"
    TOPIC = "TOPIC"
    DOMAIN = "DOMAIN"
    METHODOLOGY = "METHODOLOGY"
    PROCESS = "PROCESS"
    PRINCIPLE = "PRINCIPLE"
    THEORY = "THEORY"
    TECHNOLOGY = "TECHNOLOGY"
    BUSINESS_CONCEPT = "BUSINESS_CONCEPT"
    ABSTRACT_CONCEPT = "ABSTRACT_CONCEPT"
    KEYWORD = "KEYWORD"
    TECHNICAL_TERM = "TECHNICAL_TERM"


@dataclass
class Concept:
    """Represents an extracted concept"""
    name: str
    concept_type: ConceptType
    confidence: float
    frequency: int
    importance_score: float
    context_examples: List[str]
    related_terms: List[str]
    definition: Optional[str]
    extraction_method: str
    metadata: Dict[str, Any]
    semantic_cluster: Optional[int] = None


class ConceptExtractor:
    """Enhanced concept extractor using multiple methods"""
    
    def __init__(self):
        self.spacy_model = None
        self.sentence_transformer = None
        self.tfidf_vectorizer = None
        self.concept_patterns = self._load_concept_patterns()
        self.domain_vocabularies = self._load_domain_vocabularies()
        self.min_frequency = 2
        self.min_confidence = 0.3
        
        # Initialize models
        self._initialize_models()
        
        # Concept indicators
        self.concept_indicators = {
            ConceptType.METHODOLOGY: [
                "approach", "method", "methodology", "technique", "strategy",
                "framework", "process", "procedure", "system", "way"
            ],
            ConceptType.THEORY: [
                "theory", "hypothesis", "principle", "law", "theorem",
                "concept", "idea", "notion", "paradigm", "model"
            ],
            ConceptType.TECHNOLOGY: [
                "technology", "system", "platform", "tool", "software",
                "algorithm", "protocol", "standard", "interface", "architecture"
            ],
            ConceptType.BUSINESS_CONCEPT: [
                "strategy", "model", "framework", "process", "approach",
                "solution", "service", "product", "market", "customer"
            ]
        }
    
    def _initialize_models(self):
        """Initialize NLP models for concept extraction"""
        
        if SPACY_AVAILABLE:
            try:
                self.spacy_model = spacy.load("en_core_web_sm")
                logger.info("spaCy model loaded for concept extraction")
            except OSError:
                logger.warning("spaCy model not found for concept extraction")
                self.spacy_model = None
        
        if ML_AVAILABLE:
            try:
                self.sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")
                self.tfidf_vectorizer = TfidfVectorizer(
                    max_features=1000,
                    stop_words='english',
                    ngram_range=(1, 3)
                )
                logger.info("ML models loaded for concept extraction")
            except Exception as e:
                logger.warning(f"Failed to load ML models: {e}")
                self.sentence_transformer = None
                self.tfidf_vectorizer = None
    
    async def extract_concepts(
        self,
        text: str,
        concept_types: Optional[List[ConceptType]] = None,
        use_tfidf: bool = True,
        use_clustering: bool = True,
        use_patterns: bool = True,
        use_domain_knowledge: bool = True,
        max_concepts: int = 50
    ) -> List[Concept]:
        """Extract concepts from text using multiple methods"""
        
        all_concepts = []
        
        try:
            # Method 1: TF-IDF based extraction
            if use_tfidf and self.tfidf_vectorizer:
                tfidf_concepts = await self._extract_with_tfidf(text, concept_types)
                all_concepts.extend(tfidf_concepts)
            
            # Method 2: Pattern-based extraction
            if use_patterns:
                pattern_concepts = await self._extract_with_patterns(text, concept_types)
                all_concepts.extend(pattern_concepts)
            
            # Method 3: Domain knowledge based extraction
            if use_domain_knowledge:
                domain_concepts = await self._extract_with_domain_knowledge(text, concept_types)
                all_concepts.extend(domain_concepts)
            
            # Method 4: Linguistic analysis
            if self.spacy_model:
                linguistic_concepts = await self._extract_with_linguistics(text, concept_types)
                all_concepts.extend(linguistic_concepts)
            
            # Method 5: Semantic clustering
            if use_clustering and self.sentence_transformer:
                clustered_concepts = await self._extract_with_clustering(text, all_concepts)
                all_concepts.extend(clustered_concepts)
            
            # Merge and deduplicate concepts
            merged_concepts = await self._merge_concepts(all_concepts)
            
            # Calculate importance scores
            scored_concepts = await self._calculate_importance_scores(merged_concepts, text)
            
            # Filter and rank concepts
            filtered_concepts = self._filter_and_rank_concepts(
                scored_concepts, concept_types, max_concepts
            )
            
            return filtered_concepts
            
        except Exception as e:
            logger.error(f"Error in concept extraction: {e}")
            return []
    
    async def extract_concept_hierarchy(
        self,
        text: str,
        concepts: Optional[List[Concept]] = None
    ) -> Dict[str, Any]:
        """Extract concepts and organize them into a hierarchy"""
        
        if concepts is None:
            concepts = await self.extract_concepts(text)
        
        hierarchy = {
            "root_concepts": [],
            "concept_relationships": {},
            "concept_clusters": {},
            "abstraction_levels": {}
        }
        
        # Group concepts by type
        concepts_by_type = defaultdict(list)
        for concept in concepts:
            concepts_by_type[concept.concept_type].append(concept)
        
        # Identify root concepts (high importance, broad scope)
        root_concepts = [
            c for c in concepts 
            if c.importance_score > 0.7 and c.concept_type in [
                ConceptType.THEME, ConceptType.DOMAIN, ConceptType.THEORY
            ]
        ]
        hierarchy["root_concepts"] = [c.name for c in root_concepts]
        
        # Build concept relationships
        for concept in concepts:
            related = self._find_related_concepts(concept, concepts, text)
            hierarchy["concept_relationships"][concept.name] = related
        
        # Create semantic clusters if available
        if self.sentence_transformer and ML_AVAILABLE:
            clusters = await self._create_concept_clusters(concepts)
            hierarchy["concept_clusters"] = clusters
        
        # Determine abstraction levels
        abstraction_levels = self._determine_abstraction_levels(concepts)
        hierarchy["abstraction_levels"] = abstraction_levels
        
        return hierarchy
    
    async def analyze_concept_evolution(
        self,
        texts: List[str],
        time_points: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Analyze how concepts evolve across multiple texts/time points"""
        
        if time_points is None:
            time_points = [f"T{i}" for i in range(len(texts))]
        
        evolution_analysis = {
            "concept_timeline": {},
            "emerging_concepts": [],
            "declining_concepts": [],
            "stable_concepts": [],
            "concept_transitions": {}
        }
        
        # Extract concepts for each text
        text_concepts = []
        for text in texts:
            concepts = await self.extract_concepts(text)
            text_concepts.append(concepts)
        
        # Track concept evolution
        all_concept_names = set()
        for concepts in text_concepts:
            all_concept_names.update(c.name for c in concepts)
        
        for concept_name in all_concept_names:
            timeline = []
            for i, concepts in enumerate(text_concepts):
                concept_scores = [c.importance_score for c in concepts if c.name == concept_name]
                avg_score = sum(concept_scores) / len(concept_scores) if concept_scores else 0
                timeline.append(avg_score)
            
            evolution_analysis["concept_timeline"][concept_name] = {
                "timeline": timeline,
                "time_points": time_points
            }
            
            # Classify concept evolution
            if self._is_emerging_concept(timeline):
                evolution_analysis["emerging_concepts"].append(concept_name)
            elif self._is_declining_concept(timeline):
                evolution_analysis["declining_concepts"].append(concept_name)
            elif self._is_stable_concept(timeline):
                evolution_analysis["stable_concepts"].append(concept_name)
        
        return evolution_analysis
    
    # Extraction method implementations
    async def _extract_with_tfidf(
        self,
        text: str,
        concept_types: Optional[List[ConceptType]] = None
    ) -> List[Concept]:
        """Extract concepts using TF-IDF analysis"""
        
        if not self.tfidf_vectorizer:
            return []
        
        def extract():
            # Split text into sentences for TF-IDF analysis
            sentences = [s.strip() for s in text.split('.') if s.strip()]
            
            if len(sentences) < 2:
                return []
            
            try:
                # Fit TF-IDF on sentences
                tfidf_matrix = self.tfidf_vectorizer.fit_transform(sentences)
                feature_names = self.tfidf_vectorizer.get_feature_names_out()
                
                # Calculate average TF-IDF scores
                mean_scores = np.mean(tfidf_matrix.toarray(), axis=0)
                
                # Get top scoring terms
                top_indices = np.argsort(mean_scores)[::-1][:50]
                
                concepts = []
                for idx in top_indices:
                    term = feature_names[idx]
                    score = mean_scores[idx]
                    
                    if score > 0.1:  # Minimum TF-IDF threshold
                        concept_type = self._classify_concept_type(term)
                        
                        if concept_types is None or concept_type in concept_types:
                            concept = Concept(
                                name=term,
                                concept_type=concept_type,
                                confidence=min(score * 2, 1.0),
                                frequency=text.lower().count(term.lower()),
                                importance_score=score,
                                context_examples=self._find_context_examples(term, text),
                                related_terms=[],
                                definition=None,
                                extraction_method="tfidf",
                                metadata={
                                    "tfidf_score": score,
                                    "term_frequency": text.lower().count(term.lower())
                                }
                            )
                            concepts.append(concept)
                
                return concepts
                
            except Exception as e:
                logger.warning(f"TF-IDF extraction failed: {e}")
                return []
        
        return await asyncio.to_thread(extract)
    
    async def _extract_with_patterns(
        self,
        text: str,
        concept_types: Optional[List[ConceptType]] = None
    ) -> List[Concept]:
        """Extract concepts using pattern matching"""
        
        concepts = []
        
        for concept_type, patterns in self.concept_patterns.items():
            if concept_types and concept_type not in concept_types:
                continue
            
            for pattern_info in patterns:
                pattern = pattern_info["pattern"]
                confidence = pattern_info["confidence"]
                
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    term = match.group()
                    
                    if len(term) > 2:  # Filter very short terms
                        frequency = text.lower().count(term.lower())
                        
                        if frequency >= self.min_frequency:
                            concept = Concept(
                                name=term,
                                concept_type=concept_type,
                                confidence=confidence,
                                frequency=frequency,
                                importance_score=confidence * math.log(frequency + 1),
                                context_examples=self._find_context_examples(term, text),
                                related_terms=[],
                                definition=pattern_info.get("definition"),
                                extraction_method="patterns",
                                metadata={
                                    "pattern_name": pattern_info["name"],
                                    "regex_pattern": pattern
                                }
                            )
                            concepts.append(concept)
        
        return concepts
    
    async def _extract_with_domain_knowledge(
        self,
        text: str,
        concept_types: Optional[List[ConceptType]] = None
    ) -> List[Concept]:
        """Extract concepts using domain-specific vocabularies"""
        
        concepts = []
        text_lower = text.lower()
        
        for domain, vocabulary in self.domain_vocabularies.items():
            for term_info in vocabulary:
                term = term_info["term"]
                concept_type = term_info["concept_type"]
                confidence = term_info["confidence"]
                
                if concept_types and concept_type not in concept_types:
                    continue
                
                if term.lower() in text_lower:
                    frequency = text_lower.count(term.lower())
                    
                    if frequency >= self.min_frequency:
                        concept = Concept(
                            name=term,
                            concept_type=concept_type,
                            confidence=confidence,
                            frequency=frequency,
                            importance_score=confidence * math.log(frequency + 1),
                            context_examples=self._find_context_examples(term, text),
                            related_terms=term_info.get("related_terms", []),
                            definition=term_info.get("definition"),
                            extraction_method="domain_knowledge",
                            metadata={
                                "domain": domain,
                                "vocabulary_source": "predefined"
                            }
                        )
                        concepts.append(concept)
        
        return concepts
    
    async def _extract_with_linguistics(
        self,
        text: str,
        concept_types: Optional[List[ConceptType]] = None
    ) -> List[Concept]:
        """Extract concepts using linguistic analysis"""
        
        if not self.spacy_model:
            return []
        
        def extract():
            doc = self.spacy_model(text)
            concepts = []
            
            # Extract noun phrases as potential concepts
            noun_phrases = [chunk.text for chunk in doc.noun_chunks]
            
            # Count frequencies
            phrase_counts = Counter(noun_phrases)
            
            for phrase, frequency in phrase_counts.items():
                if frequency >= self.min_frequency and len(phrase) > 2:
                    # Analyze the phrase
                    phrase_doc = self.spacy_model(phrase)
                    
                    # Determine concept type based on linguistic features
                    concept_type = self._classify_linguistic_concept(phrase_doc)
                    
                    if concept_types is None or concept_type in concept_types:
                        # Calculate confidence based on linguistic features
                        confidence = self._calculate_linguistic_confidence(phrase_doc, frequency)
                        
                        if confidence >= self.min_confidence:
                            concept = Concept(
                                name=phrase,
                                concept_type=concept_type,
                                confidence=confidence,
                                frequency=frequency,
                                importance_score=confidence * math.log(frequency + 1),
                                context_examples=self._find_context_examples(phrase, text),
                                related_terms=[],
                                definition=None,
                                extraction_method="linguistics",
                                metadata={
                                    "pos_tags": [token.pos_ for token in phrase_doc],
                                    "dependency_labels": [token.dep_ for token in phrase_doc],
                                    "named_entities": [ent.label_ for ent in phrase_doc.ents]
                                }
                            )
                            concepts.append(concept)
            
            return concepts
        
        return await asyncio.to_thread(extract)
    
    async def _extract_with_clustering(
        self,
        text: str,
        existing_concepts: List[Concept]
    ) -> List[Concept]:
        """Extract additional concepts using semantic clustering"""
        
        if not self.sentence_transformer or not ML_AVAILABLE:
            return []
        
        def extract():
            # Get concept names and their contexts
            concept_texts = []
            for concept in existing_concepts:
                concept_texts.append(concept.name)
                concept_texts.extend(concept.context_examples[:2])  # Add some context
            
            if len(concept_texts) < 5:
                return []
            
            try:
                # Generate embeddings
                embeddings = self.sentence_transformer.encode(concept_texts)
                
                # Perform clustering
                n_clusters = min(10, len(concept_texts) // 3)
                kmeans = KMeans(n_clusters=n_clusters, random_state=42)
                cluster_labels = kmeans.fit_predict(embeddings)
                
                # Identify cluster representatives as new concepts
                new_concepts = []
                for cluster_id in range(n_clusters):
                    cluster_indices = np.where(cluster_labels == cluster_id)[0]
                    
                    if len(cluster_indices) > 1:
                        # Find cluster centroid
                        cluster_embeddings = embeddings[cluster_indices]
                        centroid = np.mean(cluster_embeddings, axis=0)
                        
                        # Find closest text to centroid
                        similarities = cosine_similarity([centroid], cluster_embeddings)[0]
                        best_idx = cluster_indices[np.argmax(similarities)]
                        cluster_representative = concept_texts[best_idx]
                        
                        # Create concept if it's not already in existing concepts
                        if not any(c.name.lower() == cluster_representative.lower() for c in existing_concepts):
                            concept = Concept(
                                name=cluster_representative,
                                concept_type=ConceptType.THEME,
                                confidence=0.6,
                                frequency=text.lower().count(cluster_representative.lower()),
                                importance_score=0.6,
                                context_examples=self._find_context_examples(cluster_representative, text),
                                related_terms=[],
                                definition=None,
                                extraction_method="clustering",
                                metadata={
                                    "cluster_id": cluster_id,
                                    "cluster_size": len(cluster_indices),
                                    "similarity_score": float(np.max(similarities))
                                },
                                semantic_cluster=cluster_id
                            )
                            new_concepts.append(concept)
                
                return new_concepts
                
            except Exception as e:
                logger.warning(f"Clustering extraction failed: {e}")
                return []
        
        return await asyncio.to_thread(extract)
    
    def _classify_concept_type(self, term: str) -> ConceptType:
        """Classify a term into a concept type"""
        
        term_lower = term.lower()
        
        # Check for specific indicators
        for concept_type, indicators in self.concept_indicators.items():
            if any(indicator in term_lower for indicator in indicators):
                return concept_type
        
        # Default classification based on term characteristics
        if len(term.split()) > 2:
            return ConceptType.ABSTRACT_CONCEPT
        elif term.endswith(('tion', 'sion', 'ment', 'ness')):
            return ConceptType.ABSTRACT_CONCEPT
        elif term.endswith(('ing', 'ed')):
            return ConceptType.PROCESS
        elif term.isupper():
            return ConceptType.TECHNICAL_TERM
        else:
            return ConceptType.KEYWORD
    
    def _classify_linguistic_concept(self, phrase_doc) -> ConceptType:
        """Classify concept type based on linguistic features"""
        
        # Check for named entities
        if phrase_doc.ents:
            ent_label = phrase_doc.ents[0].label_
            if ent_label in ["ORG", "PRODUCT"]:
                return ConceptType.TECHNOLOGY
            elif ent_label in ["EVENT", "LAW"]:
                return ConceptType.PRINCIPLE
        
        # Check POS patterns
        pos_tags = [token.pos_ for token in phrase_doc]
        
        if "VERB" in pos_tags:
            return ConceptType.PROCESS
        elif pos_tags.count("NOUN") > 1:
            return ConceptType.ABSTRACT_CONCEPT
        elif "ADJ" in pos_tags and "NOUN" in pos_tags:
            return ConceptType.THEME
        else:
            return ConceptType.KEYWORD
    
    def _calculate_linguistic_confidence(self, phrase_doc, frequency: int) -> float:
        """Calculate confidence based on linguistic features"""
        
        confidence = 0.5  # Base confidence
        
        # Boost for named entities
        if phrase_doc.ents:
            confidence += 0.2
        
        # Boost for proper nouns
        if any(token.pos_ == "PROPN" for token in phrase_doc):
            confidence += 0.1
        
        # Boost for longer phrases
        if len(phrase_doc) > 2:
            confidence += 0.1
        
        # Boost for frequency
        confidence += min(0.2, frequency * 0.05)
        
        return min(confidence, 1.0)
    
    def _find_context_examples(self, term: str, text: str, max_examples: int = 3) -> List[str]:
        """Find context examples for a term"""
        
        examples = []
        sentences = text.split('.')
        
        for sentence in sentences:
            if term.lower() in sentence.lower() and len(examples) < max_examples:
                examples.append(sentence.strip())
        
        return examples
    
    async def _merge_concepts(self, concepts: List[Concept]) -> List[Concept]:
        """Merge similar and duplicate concepts"""
        
        if not concepts:
            return []
        
        # Group concepts by similarity
        concept_groups = defaultdict(list)
        processed = set()
        
        for i, concept in enumerate(concepts):
            if i in processed:
                continue
            
            group_key = concept.name.lower()
            concept_groups[group_key].append(concept)
            processed.add(i)
            
            # Find similar concepts
            for j, other_concept in enumerate(concepts[i+1:], i+1):
                if j in processed:
                    continue
                
                if self._are_concepts_similar(concept, other_concept):
                    concept_groups[group_key].append(other_concept)
                    processed.add(j)
        
        # Merge concept groups
        merged_concepts = []
        for group in concept_groups.values():
            if len(group) == 1:
                merged_concepts.append(group[0])
            else:
                merged_concept = self._merge_concept_group(group)
                merged_concepts.append(merged_concept)
        
        return merged_concepts
    
    def _are_concepts_similar(self, concept1: Concept, concept2: Concept) -> bool:
        """Check if two concepts are similar enough to merge"""
        
        # Exact match
        if concept1.name.lower() == concept2.name.lower():
            return True
        
        # Substring match
        if concept1.name.lower() in concept2.name.lower() or concept2.name.lower() in concept1.name.lower():
            return True
        
        # Similar words
        words1 = set(concept1.name.lower().split())
        words2 = set(concept2.name.lower().split())
        
        if len(words1.intersection(words2)) / len(words1.union(words2)) > 0.5:
            return True
        
        return False
    
    def _merge_concept_group(self, group: List[Concept]) -> Concept:
        """Merge a group of similar concepts"""
        
        # Use the concept with highest importance as base
        base_concept = max(group, key=lambda x: x.importance_score)
        
        # Combine frequencies
        total_frequency = sum(c.frequency for c in group)
        
        # Average confidence
        avg_confidence = sum(c.confidence for c in group) / len(group)
        
        # Combine context examples
        all_examples = []
        for concept in group:
            all_examples.extend(concept.context_examples)
        unique_examples = list(set(all_examples))[:5]
        
        # Combine related terms
        all_related = []
        for concept in group:
            all_related.extend(concept.related_terms)
        unique_related = list(set(all_related))
        
        # Create merged concept
        merged_concept = Concept(
            name=base_concept.name,
            concept_type=base_concept.concept_type,
            confidence=min(avg_confidence * 1.1, 1.0),
            frequency=total_frequency,
            importance_score=base_concept.importance_score * 1.2,
            context_examples=unique_examples,
            related_terms=unique_related,
            definition=base_concept.definition,
            extraction_method="+".join(set(c.extraction_method for c in group)),
            metadata={
                "merged_from": len(group),
                "original_names": [c.name for c in group],
                "original_methods": [c.extraction_method for c in group]
            }
        )
        
        return merged_concept
    
    async def _calculate_importance_scores(
        self,
        concepts: List[Concept],
        text: str
    ) -> List[Concept]:
        """Calculate importance scores for concepts"""
        
        text_length = len(text)
        total_concepts = len(concepts)
        
        for concept in concepts:
            # Base score from extraction method
            base_score = concept.importance_score
            
            # Frequency component
            frequency_score = math.log(concept.frequency + 1) / math.log(text_length)
            
            # Position component (early appearance bonus)
            first_occurrence = text.lower().find(concept.name.lower())
            position_score = 1.0 - (first_occurrence / text_length) if first_occurrence >= 0 else 0.5
            
            # Context richness component
            context_score = len(concept.context_examples) / 5.0
            
            # Related terms component
            related_score = len(concept.related_terms) / 10.0
            
            # Combine scores with weights
            final_score = (
                base_score * 0.4 +
                frequency_score * 0.25 +
                position_score * 0.15 +
                context_score * 0.1 +
                related_score * 0.1
            )
            
            concept.importance_score = min(final_score, 1.0)
        
        return concepts
    
    def _filter_and_rank_concepts(
        self,
        concepts: List[Concept],
        concept_types: Optional[List[ConceptType]],
        max_concepts: int
    ) -> List[Concept]:
        """Filter and rank concepts by importance"""
        
        # Filter by type
        if concept_types:
            concepts = [c for c in concepts if c.concept_type in concept_types]
        
        # Filter by confidence
        concepts = [c for c in concepts if c.confidence >= self.min_confidence]
        
        # Sort by importance score
        concepts.sort(key=lambda x: x.importance_score, reverse=True)
        
        # Return top concepts
        return concepts[:max_concepts]
    
    def _find_related_concepts(
        self,
        concept: Concept,
        all_concepts: List[Concept],
        text: str
    ) -> List[str]:
        """Find concepts related to the given concept"""
        
        related = []
        concept_context = " ".join(concept.context_examples).lower()
        
        for other_concept in all_concepts:
            if other_concept.name == concept.name:
                continue
            
            # Check if they appear in similar contexts
            other_context = " ".join(other_concept.context_examples).lower()
            
            # Simple word overlap check
            concept_words = set(concept_context.split())
            other_words = set(other_context.split())
            
            overlap = len(concept_words.intersection(other_words))
            union = len(concept_words.union(other_words))
            
            if union > 0 and overlap / union > 0.3:
                related.append(other_concept.name)
        
        return related[:5]  # Limit to top 5 related concepts
    
    async def _create_concept_clusters(self, concepts: List[Concept]) -> Dict[str, List[str]]:
        """Create semantic clusters of concepts"""
        
        if not self.sentence_transformer or len(concepts) < 3:
            return {}
        
        def cluster():
            try:
                # Generate embeddings for concept names
                concept_names = [c.name for c in concepts]
                embeddings = self.sentence_transformer.encode(concept_names)
                
                # Perform clustering
                n_clusters = min(5, len(concepts) // 2)
                kmeans = KMeans(n_clusters=n_clusters, random_state=42)
                cluster_labels = kmeans.fit_predict(embeddings)
                
                # Group concepts by cluster
                clusters = defaultdict(list)
                for concept, label in zip(concepts, cluster_labels):
                    clusters[f"cluster_{label}"].append(concept.name)
                
                return dict(clusters)
                
            except Exception as e:
                logger.warning(f"Concept clustering failed: {e}")
                return {}
        
        return await asyncio.to_thread(cluster)
    
    def _determine_abstraction_levels(self, concepts: List[Concept]) -> Dict[str, List[str]]:
        """Determine abstraction levels of concepts"""
        
        levels = {
            "high_level": [],    # Abstract themes and theories
            "medium_level": [],  # Methodologies and processes
            "low_level": []      # Specific terms and keywords
        }
        
        for concept in concepts:
            if concept.concept_type in [ConceptType.THEME, ConceptType.THEORY, ConceptType.DOMAIN]:
                levels["high_level"].append(concept.name)
            elif concept.concept_type in [ConceptType.METHODOLOGY, ConceptType.PROCESS, ConceptType.BUSINESS_CONCEPT]:
                levels["medium_level"].append(concept.name)
            else:
                levels["low_level"].append(concept.name)
        
        return levels
    
    def _is_emerging_concept(self, timeline: List[float]) -> bool:
        """Check if concept is emerging (increasing trend)"""
        if len(timeline) < 3:
            return False
        
        # Simple trend detection
        recent_avg = sum(timeline[-2:]) / 2
        early_avg = sum(timeline[:2]) / 2
        
        return recent_avg > early_avg * 1.5
    
    def _is_declining_concept(self, timeline: List[float]) -> bool:
        """Check if concept is declining (decreasing trend)"""
        if len(timeline) < 3:
            return False
        
        recent_avg = sum(timeline[-2:]) / 2
        early_avg = sum(timeline[:2]) / 2
        
        return recent_avg < early_avg * 0.5
    
    def _is_stable_concept(self, timeline: List[float]) -> bool:
        """Check if concept is stable (consistent presence)"""
        if len(timeline) < 3:
            return False
        
        # Check for consistent non-zero values
        non_zero_count = sum(1 for x in timeline if x > 0.1)
        return non_zero_count >= len(timeline) * 0.7
    
    def _load_concept_patterns(self) -> Dict[ConceptType, List[Dict[str, Any]]]:
        """Load regex patterns for concept extraction"""
        
        return {
            ConceptType.METHODOLOGY: [
                {
                    "name": "methodology_pattern",
                    "pattern": r'\b(?:approach|method|methodology|technique|strategy|framework)\s+(?:to|for|of)\s+\w+',
                    "confidence": 0.7
                }
            ],
            ConceptType.TECHNOLOGY: [
                {
                    "name": "technology_pattern",
                    "pattern": r'\b(?:AI|ML|blockchain|cloud|API|algorithm|system|platform|software)\b',
                    "confidence": 0.8
                }
            ],
            ConceptType.BUSINESS_CONCEPT: [
                {
                    "name": "business_pattern",
                    "pattern": r'\b(?:ROI|KPI|strategy|model|revenue|profit|market|customer|growth)\b',
                    "confidence": 0.7
                }
            ]
        }
    
    def _load_domain_vocabularies(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load domain-specific vocabularies"""
        
        return {
            "technology": [
                {
                    "term": "machine learning",
                    "concept_type": ConceptType.TECHNOLOGY,
                    "confidence": 0.9,
                    "related_terms": ["AI", "neural networks", "deep learning"],
                    "definition": "A method of data analysis that automates analytical model building"
                },
                {
                    "term": "artificial intelligence",
                    "concept_type": ConceptType.TECHNOLOGY,
                    "confidence": 0.9,
                    "related_terms": ["machine learning", "automation", "algorithms"]
                }
            ],
            "business": [
                {
                    "term": "digital transformation",
                    "concept_type": ConceptType.BUSINESS_CONCEPT,
                    "confidence": 0.8,
                    "related_terms": ["automation", "digitization", "innovation"]
                }
            ]
        }