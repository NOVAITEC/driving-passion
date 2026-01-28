"""
AI-powered vehicle valuation using OpenRouter.
"""

import httpx
from dataclasses import dataclass
from typing import Optional
import json

from constants import DEFAULT_AI_MODEL
from scrapers import VehicleData
from dutch_market import DutchComparable


@dataclass
class Valuation:
    """AI valuation result."""
    estimated_retail_price: int
    estimated_quick_sale_price: int
    confidence: float
    reasoning: str = ""
    pros: list = None
    cons: list = None

    def __post_init__(self):
        if self.pros is None:
            self.pros = []
        if self.cons is None:
            self.cons = []


def build_valuation_prompt(vehicle: VehicleData, comparables: list[DutchComparable]) -> str:
    """
    Build the prompt for AI valuation.

    Args:
        vehicle: The target vehicle
        comparables: List of Dutch market comparables

    Returns:
        Prompt string
    """
    # Format comparables
    comp_text = ""
    for i, comp in enumerate(comparables[:10], 1):
        comp_text += f"{i}. {comp.title} - €{comp.price_eur:,} - {comp.mileage_km:,} km"
        if comp.location:
            comp_text += f" - {comp.location}"
        comp_text += "\n"

    if not comp_text:
        comp_text = "Geen vergelijkbare auto's gevonden op de Nederlandse markt.\n"

    # Format features
    features_text = ""
    if vehicle.features:
        features_text = "\n".join(f"- {f}" for f in vehicle.features[:20])
    else:
        features_text = "Geen specifieke opties bekend"

    prompt = f"""Je bent een expert auto-taxateur gespecialiseerd in de Nederlandse markt.

DOELVOERTUIG:
- Merk/Model: {vehicle.make} {vehicle.model}
- Bouwjaar: {vehicle.year}
- Kilometerstand: {vehicle.mileage_km:,} km
- Brandstof: {vehicle.fuel_type}
- Transmissie: {vehicle.transmission}
- CO2 uitstoot: {vehicle.co2_gkm} g/km
- Eerste registratie: {vehicle.first_registration_date.strftime('%m/%Y')}
- Duitse vraagprijs: €{vehicle.price_eur:,}

OPTIES/UITRUSTING:
{features_text}

VERGELIJKBARE AUTO'S IN NEDERLAND:
{comp_text}

OPDRACHT:
Geef een realistische taxatie voor dit voertuig op de Nederlandse markt. Let op:
1. Vergelijk met de aangeboden vergelijkbare auto's
2. Houd rekening met de opties en uitrusting
3. Geef zowel een retail prijs (showroom) als een snelle verkoop prijs (handelswaarde)

Antwoord ALLEEN in dit exacte JSON formaat:
{{
    "estimatedRetailPrice": <getal>,
    "estimatedQuickSalePrice": <getal>,
    "confidence": <0.0-1.0>,
    "reasoning": "<korte uitleg in het Nederlands>",
    "pros": ["<pluspunt 1>", "<pluspunt 2>"],
    "cons": ["<aandachtspunt 1>", "<aandachtspunt 2>"]
}}"""

    return prompt


async def call_openrouter(
    prompt: str,
    api_key: str,
    model: Optional[str] = None
) -> dict:
    """
    Call OpenRouter API with the valuation prompt.

    Args:
        prompt: The valuation prompt
        api_key: OpenRouter API key
        model: Model to use (optional, uses default if not provided)

    Returns:
        Parsed JSON response from the model
    """
    model = model or DEFAULT_AI_MODEL

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://driving-passion.nl",
                "X-Title": "Driving Passion Auto Import Calculator",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Je bent een expert auto-taxateur. Antwoord altijd in valid JSON format."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 1000,
            },
            timeout=45,
        )
        response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        return json.loads(content.strip())


async def valuate_vehicle(
    vehicle: VehicleData,
    comparables: list[DutchComparable],
    api_key: str,
    model: Optional[str] = None
) -> Valuation:
    """
    Get AI valuation for a vehicle.

    Args:
        vehicle: The target vehicle
        comparables: Dutch market comparables
        api_key: OpenRouter API key
        model: Model to use (optional)

    Returns:
        Valuation result
    """
    prompt = build_valuation_prompt(vehicle, comparables)

    try:
        result = await call_openrouter(prompt, api_key, model)

        return Valuation(
            estimated_retail_price=int(result.get("estimatedRetailPrice", 0)),
            estimated_quick_sale_price=int(result.get("estimatedQuickSalePrice", 0)),
            confidence=float(result.get("confidence", 0.5)),
            reasoning=result.get("reasoning", ""),
            pros=result.get("pros", []),
            cons=result.get("cons", []),
        )

    except Exception as e:
        print(f"Valuation error: {e}")

        # Fallback: use market average if available
        if comparables:
            prices = [c.price_eur for c in comparables]
            avg_price = sum(prices) // len(prices)
            return Valuation(
                estimated_retail_price=avg_price,
                estimated_quick_sale_price=int(avg_price * 0.9),
                confidence=0.3,
                reasoning="AI taxatie mislukt, geschat op basis van marktgemiddelde.",
            )
        else:
            # Last resort: estimate based on German price + markup
            return Valuation(
                estimated_retail_price=int(vehicle.price_eur * 1.15),
                estimated_quick_sale_price=int(vehicle.price_eur * 1.05),
                confidence=0.2,
                reasoning="Geen marktdata beschikbaar, ruwe schatting op basis van Duitse prijs.",
            )


def valuation_to_dict(valuation: Valuation) -> dict:
    """Convert Valuation to dictionary for JSON serialization."""
    return {
        "estimatedRetailPrice": valuation.estimated_retail_price,
        "estimatedQuickSalePrice": valuation.estimated_quick_sale_price,
        "confidence": valuation.confidence,
        "reasoning": valuation.reasoning,
        "pros": valuation.pros,
        "cons": valuation.cons,
    }
