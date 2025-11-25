/**
 * Frontend Request Test Script
 * Frontend'in backend'e nasıl request gönderdiğini test eder
 */

// Test için Node.js veya browser console'da çalıştırılabilir

const testFrontendRequest = async () => {
  console.log("🧪 Frontend Request Test Başlatılıyor...\n");

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  
  // Test 1: Health Check
  console.log("1️⃣ Health Check Testi...");
  try {
    const healthResponse = await fetch(`${API_URL}/health`);
    const healthData = await healthResponse.json();
    console.log("   ✅ Health Check:", healthData);
  } catch (error) {
    console.error("   ❌ Health Check Hatası:", error.message);
    console.log("   💡 Backend çalışmıyor olabilir!");
    return;
  }

  // Test 2: Root Endpoint
  console.log("\n2️⃣ Root Endpoint Testi...");
  try {
    const rootResponse = await fetch(`${API_URL}/`);
    const rootData = await rootResponse.json();
    console.log("   ✅ Root Endpoint:", rootData);
  } catch (error) {
    console.error("   ❌ Root Endpoint Hatası:", error.message);
  }

  // Test 3: Companies Endpoint
  console.log("\n3️⃣ Companies Endpoint Testi...");
  try {
    const companiesResponse = await fetch(`${API_URL}/api/v1/companies`);
    const companiesData = await companiesResponse.json();
    console.log("   ✅ Companies:", companiesData);
  } catch (error) {
    console.error("   ❌ Companies Endpoint Hatası:", error.message);
  }

  // Test 4: Scrape Request (Örnek)
  console.log("\n4️⃣ Scrape Request Testi (Örnek)...");
  const testRequest = {
    branch: "trafik",
    companies: ["Sompo", "Koru"],
    trafik_data: {
      tckn: "12345678901",
      email: "test@example.com",
      telefon: "5551234567",
      dogum_tarihi: "01/01/1990",
      plaka: "34ABC123",
      ruhsat_seri_no: "FC993016",
      arac_marka: "Volkswagen",
      arac_modeli: "Golf"
    }
  };

  try {
    console.log("   📤 Gönderilen Request:", JSON.stringify(testRequest, null, 2));
    const scrapeResponse = await fetch(`${API_URL}/api/v1/scrape/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(testRequest)
    });

    if (!scrapeResponse.ok) {
      const errorText = await scrapeResponse.text();
      throw new Error(`HTTP ${scrapeResponse.status}: ${errorText}`);
    }

    const scrapeData = await scrapeResponse.json();
    console.log("   ✅ Scrape Response:", scrapeData);
    
    if (scrapeData.request_id) {
      console.log(`   📋 Request ID: ${scrapeData.request_id}`);
      console.log(`   🔗 Durum sorgulama: GET ${API_URL}/api/v1/scrape/${scrapeData.request_id}`);
    }
  } catch (error) {
    console.error("   ❌ Scrape Request Hatası:", error.message);
  }

  console.log("\n" + "=".repeat(50));
  console.log("✅ Frontend Request Testi Tamamlandı!");
  console.log("=".repeat(50));
};

// Browser'da çalıştırmak için
if (typeof window !== 'undefined') {
  window.testFrontendRequest = testFrontendRequest;
  console.log("💡 Browser console'da testFrontendRequest() çalıştırabilirsiniz");
}

// Node.js'de çalıştırmak için
if (typeof module !== 'undefined' && module.exports) {
  module.exports = testFrontendRequest;
}

