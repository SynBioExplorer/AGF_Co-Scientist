# Phase 5B: Specialized Tool Integration

## Overview

Implement integration with specialized scientific tools and databases as mentioned in the Google paper (Section 3.5): "specialized AI models like AlphaFold", "domain-specific tools, such as open databases".

**Branch:** `phase5/tools`
**Worktree:** `worktree-5b-tools`
**Dependencies:** Phase 4 complete
**Estimated Duration:** 2 weeks

## Motivation

From the Google paper:
> "The co-scientist leverages various tools during the generation, review, and improvement of hypotheses and research proposals. Web search and retrieval are primary tools... For research goals that explore a constrained space of possibilities (e.g., all known cell receptors of a specific type or all FDA-approved drugs), the co-scientist agents utilize domain-specific tools, such as open databases, to constrain searches and generate hypotheses."

## Deliverables

### Files to Create

```
src/
├── tools/
│   ├── __init__.py
│   ├── base.py                # Abstract tool interface
│   ├── registry.py            # Tool registry for dynamic loading
│   ├── pubmed.py              # PubMed/NCBI API
│   ├── drugbank.py            # DrugBank database
│   ├── chembl.py              # ChEMBL compound database
│   ├── alphafold.py           # AlphaFold structure prediction
│   ├── uniprot.py             # UniProt protein database
│   └── clinicaltrials.py      # ClinicalTrials.gov API

tests/
└── test_tools.py              # Tool integration tests
```

### 1. Tool Interface (`src/tools/base.py`)

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class ToolResult(BaseModel):
    """Result from tool execution."""
    tool_name: str
    query: str
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}

class BaseTool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool identifier."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for agent prompts."""
        pass

    @abstractmethod
    async def execute(self, query: str, **kwargs) -> ToolResult:
        """Execute the tool with given query."""
        pass

    def get_prompt_description(self) -> str:
        """Get description for including in agent prompts."""
        return f"**{self.name}**: {self.description}"
```

### 2. Tool Registry (`src/tools/registry.py`)

```python
from typing import Dict, List, Optional, Type
from .base import BaseTool

class ToolRegistry:
    """Registry for dynamically loading and managing tools."""

    _instance = None
    _tools: Dict[str, BaseTool] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Get tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_all_descriptions(self) -> str:
        """Get all tool descriptions for prompts."""
        return "\n".join([
            tool.get_prompt_description()
            for tool in self._tools.values()
        ])

    def get_tools_for_domain(self, domain: str) -> List[BaseTool]:
        """Get tools relevant to a scientific domain."""
        domain_tools = {
            "drug_repurposing": ["pubmed", "drugbank", "chembl", "clinicaltrials"],
            "protein_research": ["pubmed", "uniprot", "alphafold"],
            "general": ["pubmed", "web_search"]
        }
        tool_names = domain_tools.get(domain, domain_tools["general"])
        return [self._tools[name] for name in tool_names if name in self._tools]

# Global registry instance
registry = ToolRegistry()
```

### 3. PubMed Tool (`src/tools/pubmed.py`)

```python
import aiohttp
from typing import List, Optional
from .base import BaseTool, ToolResult
from pydantic import BaseModel

class PubMedArticle(BaseModel):
    """PubMed article metadata."""
    pmid: str
    title: str
    abstract: Optional[str]
    authors: List[str]
    journal: str
    year: int
    doi: Optional[str]

class PubMedTool(BaseTool):
    """PubMed/NCBI E-utilities API integration."""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key  # Optional but increases rate limit

    @property
    def name(self) -> str:
        return "pubmed"

    @property
    def description(self) -> str:
        return "Search PubMed for biomedical literature. Returns article titles, abstracts, and metadata."

    async def execute(self, query: str, max_results: int = 10, **kwargs) -> ToolResult:
        """Search PubMed and return articles."""
        try:
            # Step 1: Search for PMIDs
            pmids = await self._search(query, max_results)

            if not pmids:
                return ToolResult(
                    tool_name=self.name,
                    query=query,
                    success=True,
                    data=[],
                    metadata={"count": 0}
                )

            # Step 2: Fetch article details
            articles = await self._fetch_details(pmids)

            return ToolResult(
                tool_name=self.name,
                query=query,
                success=True,
                data=[a.dict() for a in articles],
                metadata={"count": len(articles)}
            )

        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                query=query,
                success=False,
                data=None,
                error=str(e)
            )

    async def _search(self, query: str, max_results: int) -> List[str]:
        """Search PubMed and return PMIDs."""
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance"
        }
        if self.api_key:
            params["api_key"] = self.api_key

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/esearch.fcgi", params=params) as resp:
                data = await resp.json()
                return data.get("esearchresult", {}).get("idlist", [])

    async def _fetch_details(self, pmids: List[str]) -> List[PubMedArticle]:
        """Fetch article details for PMIDs."""
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml"
        }
        if self.api_key:
            params["api_key"] = self.api_key

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/efetch.fcgi", params=params) as resp:
                xml_text = await resp.text()
                return self._parse_xml(xml_text)

    def _parse_xml(self, xml_text: str) -> List[PubMedArticle]:
        """Parse PubMed XML response."""
        import xml.etree.ElementTree as ET
        articles = []

        root = ET.fromstring(xml_text)
        for article in root.findall(".//PubmedArticle"):
            try:
                medline = article.find("MedlineCitation")
                pmid = medline.find("PMID").text

                article_data = medline.find("Article")
                title = article_data.find("ArticleTitle").text or ""

                abstract_elem = article_data.find("Abstract/AbstractText")
                abstract = abstract_elem.text if abstract_elem is not None else None

                # Authors
                authors = []
                for author in article_data.findall(".//Author"):
                    last = author.find("LastName")
                    first = author.find("ForeName")
                    if last is not None:
                        name = last.text
                        if first is not None:
                            name = f"{first.text} {name}"
                        authors.append(name)

                # Journal
                journal_elem = article_data.find("Journal/Title")
                journal = journal_elem.text if journal_elem is not None else ""

                # Year
                year_elem = article_data.find(".//PubDate/Year")
                year = int(year_elem.text) if year_elem is not None else 0

                # DOI
                doi = None
                for id_elem in article.findall(".//ArticleId"):
                    if id_elem.get("IdType") == "doi":
                        doi = id_elem.text
                        break

                articles.append(PubMedArticle(
                    pmid=pmid,
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    journal=journal,
                    year=year,
                    doi=doi
                ))
            except Exception:
                continue

        return articles
```

### 4. DrugBank Tool (`src/tools/drugbank.py`)

```python
from typing import Optional, List
from .base import BaseTool, ToolResult
from pydantic import BaseModel

class Drug(BaseModel):
    """Drug information from DrugBank."""
    drugbank_id: str
    name: str
    description: Optional[str]
    indication: Optional[str]
    mechanism_of_action: Optional[str]
    targets: List[str]
    categories: List[str]
    approval_status: str

class DrugBankTool(BaseTool):
    """DrugBank database integration."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://go.drugbank.com/api/v1"

    @property
    def name(self) -> str:
        return "drugbank"

    @property
    def description(self) -> str:
        return "Search DrugBank for drug information including targets, mechanisms, indications, and approval status."

    async def execute(self, query: str, **kwargs) -> ToolResult:
        """Search DrugBank for drugs."""
        try:
            import aiohttp

            headers = {"Authorization": f"Bearer {self.api_key}"}

            async with aiohttp.ClientSession() as session:
                # Search endpoint
                async with session.get(
                    f"{self.base_url}/drugs",
                    params={"q": query},
                    headers=headers
                ) as resp:
                    if resp.status != 200:
                        return ToolResult(
                            tool_name=self.name,
                            query=query,
                            success=False,
                            data=None,
                            error=f"API error: {resp.status}"
                        )

                    data = await resp.json()
                    drugs = [self._parse_drug(d) for d in data.get("drugs", [])]

                    return ToolResult(
                        tool_name=self.name,
                        query=query,
                        success=True,
                        data=[d.dict() for d in drugs],
                        metadata={"count": len(drugs)}
                    )

        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                query=query,
                success=False,
                data=None,
                error=str(e)
            )

    def _parse_drug(self, data: dict) -> Drug:
        """Parse drug data from API response."""
        return Drug(
            drugbank_id=data.get("drugbank_id", ""),
            name=data.get("name", ""),
            description=data.get("description"),
            indication=data.get("indication"),
            mechanism_of_action=data.get("mechanism_of_action"),
            targets=[t.get("name", "") for t in data.get("targets", [])],
            categories=[c.get("category", "") for c in data.get("categories", [])],
            approval_status=data.get("groups", ["unknown"])[0]
        )

    async def get_fda_approved_drugs(self, category: Optional[str] = None) -> ToolResult:
        """Get list of FDA-approved drugs, optionally filtered by category."""
        query = "status:approved"
        if category:
            query += f" category:{category}"
        return await self.execute(query)
```

### 5. ChEMBL Tool (`src/tools/chembl.py`)

```python
from typing import Optional, List
from .base import BaseTool, ToolResult
from pydantic import BaseModel

class Compound(BaseModel):
    """Chemical compound from ChEMBL."""
    chembl_id: str
    name: Optional[str]
    smiles: Optional[str]
    molecular_formula: Optional[str]
    molecular_weight: Optional[float]
    max_phase: int  # Clinical trial phase (4 = approved)
    targets: List[str]

class ChEMBLTool(BaseTool):
    """ChEMBL chemical database integration."""

    BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"

    @property
    def name(self) -> str:
        return "chembl"

    @property
    def description(self) -> str:
        return "Search ChEMBL for chemical compounds, their structures, and bioactivity data."

    async def execute(self, query: str, max_results: int = 10, **kwargs) -> ToolResult:
        """Search ChEMBL for compounds."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/molecule/search",
                    params={"q": query, "limit": max_results, "format": "json"}
                ) as resp:
                    if resp.status != 200:
                        return ToolResult(
                            tool_name=self.name,
                            query=query,
                            success=False,
                            data=None,
                            error=f"API error: {resp.status}"
                        )

                    data = await resp.json()
                    compounds = [self._parse_compound(m) for m in data.get("molecules", [])]

                    return ToolResult(
                        tool_name=self.name,
                        query=query,
                        success=True,
                        data=[c.dict() for c in compounds],
                        metadata={"count": len(compounds)}
                    )

        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                query=query,
                success=False,
                data=None,
                error=str(e)
            )

    def _parse_compound(self, data: dict) -> Compound:
        """Parse compound from API response."""
        return Compound(
            chembl_id=data.get("molecule_chembl_id", ""),
            name=data.get("pref_name"),
            smiles=data.get("molecule_structures", {}).get("canonical_smiles"),
            molecular_formula=data.get("molecule_properties", {}).get("full_molformula"),
            molecular_weight=data.get("molecule_properties", {}).get("full_mwt"),
            max_phase=data.get("max_phase", 0),
            targets=[]  # Requires separate API call
        )

    async def get_compound_targets(self, chembl_id: str) -> List[str]:
        """Get targets for a specific compound."""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/mechanism",
                params={"molecule_chembl_id": chembl_id, "format": "json"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return [m.get("target_chembl_id", "") for m in data.get("mechanisms", [])]
        return []
```

### 6. AlphaFold Tool (`src/tools/alphafold.py`)

```python
from typing import Optional
from .base import BaseTool, ToolResult
from pydantic import BaseModel

class ProteinStructure(BaseModel):
    """Protein structure from AlphaFold."""
    uniprot_id: str
    gene_name: Optional[str]
    organism: str
    pdb_url: str
    confidence_score: float  # pLDDT score
    structure_coverage: float

class AlphaFoldTool(BaseTool):
    """AlphaFold protein structure database integration."""

    BASE_URL = "https://alphafold.ebi.ac.uk/api"

    @property
    def name(self) -> str:
        return "alphafold"

    @property
    def description(self) -> str:
        return "Query AlphaFold database for predicted protein structures. Useful for understanding protein targets and drug binding sites."

    async def execute(self, query: str, **kwargs) -> ToolResult:
        """Get AlphaFold structure for UniProt ID or gene name."""
        try:
            import aiohttp

            # Query could be UniProt ID or gene name
            uniprot_id = await self._resolve_uniprot_id(query)

            if not uniprot_id:
                return ToolResult(
                    tool_name=self.name,
                    query=query,
                    success=False,
                    data=None,
                    error=f"Could not find UniProt ID for: {query}"
                )

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/prediction/{uniprot_id}"
                ) as resp:
                    if resp.status != 200:
                        return ToolResult(
                            tool_name=self.name,
                            query=query,
                            success=False,
                            data=None,
                            error=f"Structure not found for: {uniprot_id}"
                        )

                    data = await resp.json()
                    structure = self._parse_structure(data)

                    return ToolResult(
                        tool_name=self.name,
                        query=query,
                        success=True,
                        data=structure.dict(),
                        metadata={"uniprot_id": uniprot_id}
                    )

        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                query=query,
                success=False,
                data=None,
                error=str(e)
            )

    async def _resolve_uniprot_id(self, query: str) -> Optional[str]:
        """Resolve gene name or protein name to UniProt ID."""
        import aiohttp

        # Check if already a UniProt ID format
        if query.startswith(("P", "Q", "O", "A")) and len(query) == 6:
            return query

        # Search UniProt
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://rest.uniprot.org/uniprotkb/search",
                params={"query": query, "format": "json", "size": 1}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        return results[0].get("primaryAccession")
        return None

    def _parse_structure(self, data: dict) -> ProteinStructure:
        """Parse structure from API response."""
        return ProteinStructure(
            uniprot_id=data.get("uniprotAccession", ""),
            gene_name=data.get("gene"),
            organism=data.get("organismScientificName", ""),
            pdb_url=data.get("pdbUrl", ""),
            confidence_score=data.get("globalMetricValue", 0.0),
            structure_coverage=data.get("modelCreatedDate", 0.0)  # Placeholder
        )

    async def get_binding_sites(self, uniprot_id: str) -> ToolResult:
        """Get predicted binding sites for a protein."""
        # This would integrate with additional tools like P2Rank
        pass
```

### 7. ClinicalTrials.gov Tool (`src/tools/clinicaltrials.py`)

```python
from typing import List, Optional
from .base import BaseTool, ToolResult
from pydantic import BaseModel

class ClinicalTrial(BaseModel):
    """Clinical trial from ClinicalTrials.gov."""
    nct_id: str
    title: str
    status: str
    phase: Optional[str]
    conditions: List[str]
    interventions: List[str]
    sponsor: str
    start_date: Optional[str]
    completion_date: Optional[str]

class ClinicalTrialsTool(BaseTool):
    """ClinicalTrials.gov API integration."""

    BASE_URL = "https://clinicaltrials.gov/api/v2"

    @property
    def name(self) -> str:
        return "clinicaltrials"

    @property
    def description(self) -> str:
        return "Search ClinicalTrials.gov for ongoing and completed clinical trials. Useful for understanding drug development status and trial designs."

    async def execute(self, query: str, max_results: int = 10, **kwargs) -> ToolResult:
        """Search for clinical trials."""
        try:
            import aiohttp

            params = {
                "query.term": query,
                "pageSize": max_results,
                "format": "json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/studies",
                    params=params
                ) as resp:
                    if resp.status != 200:
                        return ToolResult(
                            tool_name=self.name,
                            query=query,
                            success=False,
                            data=None,
                            error=f"API error: {resp.status}"
                        )

                    data = await resp.json()
                    trials = [self._parse_trial(s) for s in data.get("studies", [])]

                    return ToolResult(
                        tool_name=self.name,
                        query=query,
                        success=True,
                        data=[t.dict() for t in trials],
                        metadata={"count": len(trials)}
                    )

        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                query=query,
                success=False,
                data=None,
                error=str(e)
            )

    def _parse_trial(self, data: dict) -> ClinicalTrial:
        """Parse trial from API response."""
        protocol = data.get("protocolSection", {})
        id_module = protocol.get("identificationModule", {})
        status_module = protocol.get("statusModule", {})
        design_module = protocol.get("designModule", {})
        conditions_module = protocol.get("conditionsModule", {})
        arms_module = protocol.get("armsInterventionsModule", {})
        sponsor_module = protocol.get("sponsorCollaboratorsModule", {})

        return ClinicalTrial(
            nct_id=id_module.get("nctId", ""),
            title=id_module.get("briefTitle", ""),
            status=status_module.get("overallStatus", ""),
            phase=design_module.get("phases", [None])[0] if design_module.get("phases") else None,
            conditions=conditions_module.get("conditions", []),
            interventions=[i.get("name", "") for i in arms_module.get("interventions", [])],
            sponsor=sponsor_module.get("leadSponsor", {}).get("name", ""),
            start_date=status_module.get("startDateStruct", {}).get("date"),
            completion_date=status_module.get("completionDateStruct", {}).get("date")
        )
```

### 8. Agent Integration

Update Generation agent to use tools:

```python
# In src/agents/generation.py

class GenerationAgent(BaseAgent):
    def __init__(
        self,
        llm_client: BaseLLMClient,
        tool_registry: Optional[ToolRegistry] = None
    ):
        super().__init__(llm_client)
        self.tool_registry = tool_registry or registry

    async def execute(
        self,
        research_goal: ResearchGoal,
        method: str = "literature",
        use_tools: bool = True,
        **kwargs
    ) -> Hypothesis:
        # Determine relevant tools based on goal
        if use_tools and self.tool_registry:
            domain = self._detect_domain(research_goal.description)
            tools = self.tool_registry.get_tools_for_domain(domain)

            # Gather tool results
            tool_context = await self._gather_tool_context(research_goal, tools)
            kwargs["tool_results"] = tool_context

        # Continue with hypothesis generation
        return await super().execute(research_goal, method, **kwargs)

    def _detect_domain(self, description: str) -> str:
        """Detect research domain from goal description."""
        keywords = {
            "drug_repurposing": ["drug", "repurpos", "therapeutic", "treatment", "fda"],
            "protein_research": ["protein", "structure", "binding", "enzyme", "receptor"]
        }

        description_lower = description.lower()
        for domain, words in keywords.items():
            if any(w in description_lower for w in words):
                return domain
        return "general"

    async def _gather_tool_context(
        self,
        goal: ResearchGoal,
        tools: List[BaseTool]
    ) -> str:
        """Gather relevant context from tools."""
        results = []

        for tool in tools:
            result = await tool.execute(goal.description)
            if result.success and result.data:
                results.append(f"### {tool.name.upper()} Results\n{result.data[:3]}")

        return "\n\n".join(results)
```

## Test Cases (`tests/test_tools.py`)

```python
import pytest
from src.tools.pubmed import PubMedTool
from src.tools.chembl import ChEMBLTool
from src.tools.alphafold import AlphaFoldTool

@pytest.mark.asyncio
async def test_pubmed_search():
    """Test PubMed search."""
    tool = PubMedTool()
    result = await tool.execute("KIRA6 AML leukemia", max_results=5)

    assert result.success
    assert len(result.data) > 0
    assert all("pmid" in article for article in result.data)

@pytest.mark.asyncio
async def test_chembl_search():
    """Test ChEMBL compound search."""
    tool = ChEMBLTool()
    result = await tool.execute("aspirin", max_results=3)

    assert result.success
    assert len(result.data) > 0

@pytest.mark.asyncio
async def test_alphafold_structure():
    """Test AlphaFold structure retrieval."""
    tool = AlphaFoldTool()
    result = await tool.execute("P53")  # Well-known protein

    assert result.success
    assert "pdb_url" in result.data

@pytest.mark.asyncio
async def test_tool_registry():
    """Test tool registry functionality."""
    from src.tools.registry import registry, ToolRegistry
    from src.tools.pubmed import PubMedTool

    # Register tool
    registry.register(PubMedTool())

    assert "pubmed" in registry.list_tools()
    assert registry.get("pubmed") is not None

    # Get domain-specific tools
    drug_tools = registry.get_tools_for_domain("drug_repurposing")
    assert any(t.name == "pubmed" for t in drug_tools)
```

## Success Criteria

- [ ] PubMed search returning relevant articles
- [ ] DrugBank integration for drug information
- [ ] ChEMBL integration for compound data
- [ ] AlphaFold integration for protein structures
- [ ] ClinicalTrials.gov search working
- [ ] Tool registry with domain-based selection
- [ ] Generation agent using tools automatically
- [ ] All tests passing
- [ ] Rate limiting and error handling implemented

## Environment Variables

```bash
# Tool API Keys (some are optional)
PUBMED_API_KEY=           # Optional, increases rate limit
DRUGBANK_API_KEY=         # Required for DrugBank
CHEMBL_API_KEY=           # Optional for ChEMBL

# Tool Configuration
TOOL_TIMEOUT_SECONDS=30
TOOL_MAX_RETRIES=3
```
