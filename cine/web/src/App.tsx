import { useEffect, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { galaxy } from './api'
import { useGalaxy } from './store'
import { buildLayout } from './layout'
import GalaxyScene from './scenes/GalaxyScene'
import BootScene from './scenes/BootScene'
import HUD from './components/HUD'
import Navigator from './components/Navigator'
import Detail from './pages/Detail'
import Profile from './pages/Profile'
import Chat from './pages/Chat'
import Login from './pages/Login'
import Account from './pages/Account'
import Guest from './pages/Guest'
import About from './pages/About'
import List from './pages/List'
import Explore from './pages/Explore'
import Personality from './pages/Personality'

interface Route { path: string; params: Record<string, string> }

function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>({ path: '/', params: {} })
  useEffect(() => {
    const onHash = () => {
      const hash = location.hash || '#/'
      const base = hash.split('?')[0]
      const params: Record<string, string> = {}
      new URLSearchParams(hash.split('?')[1] || '').forEach((v, k) => { params[k] = v })
      const m = base.match(/^#\/movie\/([\w]+)/)
      if (m) { setRoute({ path: '/movie', params: { id: m[1] } }); return }
      setRoute({ path: base.replace(/^#/, '') || '/', params })
    }
    onHash()
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  return route
}

export default function App() {
  const route = useHashRoute()
  const setPlanets = useGalaxy((s) => s.setPlanets)
  const setBooted = useGalaxy((s) => s.setBooted)
  const setSelected = useGalaxy((s) => s.setSelected)

  /* 首帧：加载 5000 颗星球（590 核心 + 库外精选）+ 判断是否需要开场 */
  useEffect(() => {
    void galaxy().then((d) => { buildLayout(d.planets); setPlanets(d.planets) }).catch(() => { /* 后端未启时静默 */ })
    if (sessionStorage.getItem('cine_booted')) setBooted(true)
  }, [setPlanets, setBooted])

  /* 进入详情页前记住来源页（详情页退出时回到来源，而不是一律跳回银河） */
  useEffect(() => {
    if (route.path === '/movie') {
      sessionStorage.setItem('cine_detail_from', sessionStorage.getItem('cine_route_now') || '/')
    }
    sessionStorage.setItem('cine_route_now', route.path)
  }, [route])

  /* 镜头同步：进入电影空间时飞向该星 */
  useEffect(() => {
    if (route.path === '/movie' && route.params.id) {
      setSelected(route.params.id)
      sessionStorage.setItem('cine_booted', '1')
    } else {
      setSelected(null)
    }
  }, [route, setSelected])

  return (
    <>
      <GalaxyScene />
      <HUD />
      <AnimatePresence>
        {route.path === '/movie' && route.params.id && (
          <Detail key={route.params.id} id={route.params.id} />
        )}
        {route.path === '/profile' && <Profile key="profile" />}
        {route.path === '/chat' && <Chat key="chat" movieId={route.params.movie_id} />}
        {route.path === '/login' && <Login key="login" />}
        {route.path === '/account' && <Account key="account" />}
        {route.path === '/guest' && <Guest key="guest" />}
        {route.path === '/about' && <About key="about" />}
        {route.path === '/list' && <List key="list" />}
        {route.path === '/explore' && <Explore key="explore" />}
        {route.path === '/personality' && <Personality key="personality" />}
      </AnimatePresence>
      <Navigator />
      <BootScene />
    </>
  )
}
