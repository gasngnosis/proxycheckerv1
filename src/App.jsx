import { useState, useEffect, useRef } from 'react'
import { Shield, Activity, Copy, Download, Check, X, Cloud, ArrowDown, RefreshCw } from 'lucide-react'
import axios from 'axios'

function App() {
  const [inputText, setInputText] = useState('')
  const [proxies, setProxies] = useState([])
  const [results, setResults] = useState([])
  const [isTesting, setIsTesting] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stats, setStats] = useState({
    total: 0,
    good: 0,
    bad: 0
  })
  const [cachedProxies, setCachedProxies] = useState([])
  const [lastFetchTimestamp, setLastFetchTimestamp] = useState(null)
  const [isFetchingCached, setIsFetchingCached] = useState(false)
  const [fetchError, setFetchError] = useState(null)
  const [showAnimation, setShowAnimation] = useState(false)
  const [goodProxiesFromLastTest, setGoodProxiesFromLastTest] = useState([])
  const [notifications, setNotifications] = useState([])
  const [isRetesting, setIsRetesting] = useState(false)
  const websocketRef = useRef(null)

  const showNotification = (message, type = 'info') => {
    const id = Date.now()
    setNotifications(prev => [...prev, { id, message, type }])

    // Auto-remove notification after 5 seconds
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id))
    }, 5000)
  }

  const extractProxies = () => {
    // Simple regex to extract IP:PORT patterns
    const pattern = /(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})/g
    const matches = inputText.match(pattern) || []
    return matches
  }

  const fetchCachedProxies = async () => {
    setIsFetchingCached(true)
    setFetchError(null)

    try {
      // Use the new pre-verified proxies endpoint
      const response = await axios.get('http://localhost:8000/api/get-preverified-proxies')
      if (response.data.success) {
        setCachedProxies(response.data.proxies)
        setLastFetchTimestamp(response.data.timestamp)
        return response.data.proxies
      } else {
        throw new Error('Failed to fetch pre-verified proxies')
      }
    } catch (error) {
      console.error('Error fetching pre-verified proxies:', error)
      setFetchError('Provider Unavailable - Using Last Cached List')
      // Return empty array on error
      return []
    } finally {
      setIsFetchingCached(false)
    }
  }

  const handleSmartFill = async () => {
    setShowAnimation(true)

    try {
      const proxies = await fetchCachedProxies()
      if (proxies && proxies.length > 0) {
        // Format proxies as one per line
        const proxyText = proxies.join('\n')
        setInputText(proxyText)

        // Show success notification with pre-verified info
        setTimeout(() => {
          setShowAnimation(false)
          showNotification(`✅ Loaded ${proxies.length} pre-verified working proxies! These proxies have been tested on the server and are guaranteed to work. No browser testing needed!`, 'success')
        }, 1000)
      } else {
        setShowAnimation(false)
        showNotification('No pre-verified proxies available', 'warning')
      }
    } catch (error) {
      setShowAnimation(false)
      console.error('Error in smart fill:', error)
      showNotification('Error loading pre-verified proxies. Please try again.', 'error')
    }
  }

  const handleTestProxies = async () => {
    const extractedProxies = extractProxies()
    if (extractedProxies.length === 0) {
      showNotification('No valid proxies found in the input text', 'warning')
      return
    }

    setProxies(extractedProxies)
    setResults([])
    setIsTesting(true)
    setProgress(0)
    setStats({
      total: extractedProxies.length,
      good: 0,
      bad: 0
    })

    // Close existing WebSocket connection if any
    if (websocketRef.current) {
      websocketRef.current.close()
    }

    try {
      // Connect to WebSocket
      const ws = new WebSocket('ws://localhost:8000/ws/verify')
      websocketRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected')
        ws.send(JSON.stringify({ text: inputText }))
      }

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)

        if (data.type === 'start') {
          console.log('Starting proxy testing...')
        } else if (data.type === 'result') {
          // Update results in real-time
          setResults(prevResults => {
            // Check if this result already exists
            const exists = prevResults.some(r => r.proxy === data.result.proxy)
            if (!exists) {
              return [...prevResults, data.result]
            }
            return prevResults
          })

          // Update progress
          setProgress(data.progress)

          // Update stats
          setStats(prevStats => {
            if (data.result.success) {
              return {
                ...prevStats,
                good: prevStats.good + 1
              }
            } else {
              return {
                ...prevStats,
                bad: prevStats.bad + 1
              }
            }
          })
        } else if (data.type === 'complete') {
          console.log('Proxy testing complete')
          setIsTesting(false)
          setIsRetesting(false)
          // Store good proxies from this test for potential retesting
          const goodProxies = results.filter(r => r.success).map(r => r.proxy)
          setGoodProxiesFromLastTest(goodProxies)
          showNotification(`✅ Testing complete! Found ${goodProxies.length} good proxies`, 'success')
        } else if (data.type === 'error') {
          console.error('WebSocket error:', data.message)
          showNotification('Error testing proxies: ' + data.message, 'error')
          setIsTesting(false)
        }
      }

      ws.onclose = () => {
        console.log('WebSocket disconnected')
        setIsTesting(false)
      }

      ws.onerror = async (error) => {
        console.error('WebSocket error:', error)
        showNotification('WebSocket connection error. Falling back to HTTP.', 'warning')
        setIsTesting(false)

        // Fallback to HTTP if WebSocket fails
        try {
          const response = await axios.post('http://localhost:8000/api/verify', {
            text: inputText
          })

          const results = response.data.results
          setResults(results)

          // Update stats
          const goodCount = results.filter(r => r.success).length
          const badCount = results.filter(r => !r.success).length

          setStats({
            total: results.length,
            good: goodCount,
            bad: badCount
          })

          // Store good proxies from this test for potential retesting
          const goodProxies = results.filter(r => r.success).map(r => r.proxy)
          setGoodProxiesFromLastTest(goodProxies)

        } catch (error) {
          console.error('Error testing proxies:', error)
          showNotification('Error testing proxies. Please check console for details.', 'error')
        } finally {
          setIsTesting(false)
          setProgress(100)
        }
      }

    } catch (error) {
      console.error('Error connecting to WebSocket:', error)
      showNotification('Error connecting to WebSocket. Please check console for details.', 'error')
      setIsTesting(false)
    }
  }

  const handleCopyGoodProxies = () => {
    const goodProxies = results
      .filter(r => r.success)
      .map(r => r.proxy)
      .join('\n')

    if (goodProxies) {
      navigator.clipboard.writeText(goodProxies)
        .then(() => showNotification('Good proxies copied to clipboard!', 'success'))
        .catch(() => showNotification('Failed to copy to clipboard', 'error'))
    }
  }

  const copyGoodProxiesToTest = () => {
    if (goodProxiesFromLastTest.length === 0) {
      showNotification('No good proxies available from previous test', 'warning')
      return false
    }

    // Format good proxies as one per line
    const proxyText = goodProxiesFromLastTest.join('\n')
    setInputText(proxyText)
    showNotification(`✅ Copied ${goodProxiesFromLastTest.length} good proxies from previous test to test area`, 'success')
    return true
  }

  const handleTestAgain = async () => {
    const success = copyGoodProxiesToTest()
    if (!success) return

    // Set retesting flag
    setIsRetesting(true)
    showNotification(`🔄 Retesting ${goodProxiesFromLastTest.length} good proxies from previous test...`, 'info')

    // Wait a moment for the UI to update
    setTimeout(() => {
      handleTestProxies()
    }, 100)
  }

  const handleDownloadCSV = () => {
    const csvContent = [
      'Proxy,Status,Latency,Exit IP,Message',
      ...results.map(r =>
        `"${r.proxy}",${r.success ? 'Good' : 'Bad'},${r.latency},"${r.exit_ip}","${r.message}"`
      )
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'proxy_results.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="min-h-screen bg-[#F0F8FF] p-4">
      <div className="max-w-6xl mx-auto">
        {/* Notifications */}
        <div className="fixed top-4 right-4 z-50 space-y-2">
          {notifications.map(notification => (
            <div
              key={notification.id}
              className={`p-4 rounded-lg shadow-lg text-white max-w-sm animate-slide-in-right ${
                notification.type === 'success' ? 'bg-green-600' :
                notification.type === 'error' ? 'bg-red-600' :
                notification.type === 'warning' ? 'bg-yellow-600' :
                'bg-blue-600'
              }`}
            >
              {notification.message}
            </div>
          ))}
        </div>
        <h1 className="text-3xl font-bold text-[#007BFF] mb-6 text-center">Pre-Verified Proxy Manager</h1>

        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">Pre-Verified Proxy Manager</h2>

          {/* Smart Fill Button */}
          <div className="mb-4">
            <button
              onClick={handleSmartFill}
              disabled={isFetchingCached}
              className="w-full bg-[#007BFF] text-white py-3 px-6 rounded-lg hover:bg-blue-700 transition-colors disabled:bg-blue-300 disabled:cursor-not-allowed flex items-center justify-center"
            >
              <Cloud className="mr-2" size={18} />
              <ArrowDown className="mr-2" size={18} />
              <Shield className="mr-2" size={18} />
              {isFetchingCached ? 'Loading...' : 'Load Pre-Verified Proxies'}
            </button>
          </div>

          {/* Sync Metadata Tile */}
          {lastFetchTimestamp && (
            <div className="mb-4 p-3 bg-[#F0F8FF] rounded-lg text-sm text-gray-700 border border-blue-200">
              <div className="flex items-center">
                <Shield className="mr-2 text-[#007BFF]" size={16} />
                <span>Pre-Verified Proxies - Last updated: {new Date(lastFetchTimestamp).toLocaleString()}</span>
              </div>
            </div>
          )}

          {/* Error Feedback */}
          {fetchError && (
            <div className="mb-4 p-3 bg-yellow-100 rounded-lg text-sm text-yellow-800 border border-yellow-300">
              {fetchError}
            </div>
          )}

          {/* Glassmorphism Animation Overlay */}
          {showAnimation && (
            <div className="fixed inset-0 flex items-center justify-center z-50">
              <div className="absolute inset-0 bg-black bg-opacity-20 backdrop-blur-sm"></div>
              <div className="relative bg-white bg-opacity-80 backdrop-blur-lg p-6 rounded-lg shadow-xl max-w-md">
                <div className="text-center">
                  <div className="text-[#007BFF] text-lg font-semibold mb-2">Loading Proxies...</div>
                  <div className="text-gray-600">Populating from verified cache</div>
                </div>
              </div>
            </div>
          )}

          <textarea
            className="w-full h-40 p-4 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-[#007BFF] focus:border-transparent"
            placeholder="Paste raw proxy data here (IP:PORT format) or use 'Load Pre-Verified Proxies' button..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
          />

          <div className="flex gap-4 mt-4">
            <button
              onClick={handleTestProxies}
              disabled={isTesting || !inputText.trim()}
              className="flex-1 bg-[#007BFF] text-white py-3 px-6 rounded-lg hover:bg-blue-700 transition-colors disabled:bg-blue-300 disabled:cursor-not-allowed"
            >
              {isTesting ? (isRetesting ? 'Retesting...' : 'Testing...') : 'Test Proxies (Optional)'}
            </button>

            <button
              onClick={handleTestAgain}
              disabled={isTesting || goodProxiesFromLastTest.length === 0}
              className="bg-[#FFC107] text-white py-3 px-6 rounded-lg hover:bg-yellow-600 transition-colors disabled:bg-yellow-300 disabled:cursor-not-allowed"
            >
              <RefreshCw className="inline-block mr-2" size={16} />
              Test Again ({goodProxiesFromLastTest.length})
            </button>

            <button
              onClick={handleCopyGoodProxies}
              disabled={stats.good === 0}
              className="bg-[#28A745] text-white py-3 px-6 rounded-lg hover:bg-green-700 transition-colors disabled:bg-green-300 disabled:cursor-not-allowed"
            >
              <Copy className="inline-block mr-2" size={16} />
              Copy Good ({stats.good})
            </button>

            <button
              onClick={handleDownloadCSV}
              disabled={results.length === 0}
              className="bg-gray-600 text-white py-3 px-6 rounded-lg hover:bg-gray-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              <Download className="inline-block mr-2" size={16} />
              Download CSV
            </button>
          </div>
        </div>

        {stats.total > 0 && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">Live Dashboard</h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="bg-[#007BFF] text-white p-4 rounded-lg">
                <div className="text-sm opacity-80">Total Proxies</div>
                <div className="text-3xl font-bold">{stats.total}</div>
              </div>

              <div className="bg-[#28A745] text-white p-4 rounded-lg">
                <div className="text-sm opacity-80">Good Proxies</div>
                <div className="text-3xl font-bold">{stats.good}</div>
              </div>

              <div className="bg-[#DC3545] text-white p-4 rounded-lg">
                <div className="text-sm opacity-80">Bad Proxies</div>
                <div className="text-3xl font-bold">{stats.bad}</div>
              </div>
            </div>

            {isTesting && (
              <div className="mb-4">
                <div className="text-sm text-gray-600 mb-2 flex items-center">
                  {isRetesting ? (
                    <>
                      <RefreshCw className="mr-2 text-[#FFC107] animate-spin" size={16} />
                      Retesting Progress: {progress}%
                    </>
                  ) : (
                    <>Progress: {progress}%</>
                  )}
                </div>
                <div className="w-full bg-gray-200 rounded-full h-4">
                  <div
                    className={`h-4 rounded-full transition-all ${isRetesting ? 'bg-[#FFC107]' : 'bg-[#007BFF]'}`}
                    style={{ width: `${progress}%` }}
                  ></div>
                </div>
              </div>
            )}
          </div>
        )}

        {results.length > 0 && (
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">Validation Results</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...results].sort((a, b) => b.success - a.success).map((result, index) => (
                <div
                  key={index}
                  className={`p-4 rounded-lg ${result.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="font-mono text-lg">{result.proxy}</div>
                    {result.success ? (
                      <Check className="text-green-600" size={20} />
                    ) : (
                      <X className="text-red-600" size={20} />
                    )}
                  </div>

                  <div className="text-sm text-gray-600 mb-1">
                    Status: <span className={result.success ? 'text-green-600' : 'text-red-600'}>
                      {result.success ? 'Good' : 'Bad'}
                    </span>
                  </div>

                  {result.latency > 0 && (
                    <div className="text-sm text-gray-600 mb-1">
                      <Activity className="inline-block mr-1" size={14} />
                      Latency: {result.latency}s
                    </div>
                  )}

                  {result.exit_ip && (
                    <div className="text-sm text-gray-600 mb-1">
                      <Shield className="inline-block mr-1" size={14} />
                      Exit IP: {result.exit_ip}
                    </div>
                  )}

                  <div className="text-sm text-gray-500 mt-2">
                    {result.message}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (websocketRef.current) {
        websocketRef.current.close()
      }
    }
  }, [])
}

export default App