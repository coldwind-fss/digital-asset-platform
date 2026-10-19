import { nextTick } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
export const router=createRouter({history:createWebHistory('/'),routes:[
 {path:'/',redirect:'/dashboard'},
 {path:'/login',redirect:to=>typeof to.query.returnTo==='string'&&/^\/(dashboard|resources|my-resources|subscriptions|governance|asset-map|settings|directory)(\/|\?|$)/.test(to.query.returnTo)?to.query.returnTo:'/dashboard'},
 {path:'/dashboard',component:()=>import('../features/v3/DashboardPage.vue'),meta:{title:'工作台'}},
 {path:'/resources',component:()=>import('../features/v3/ResourcesPage.vue'),meta:{title:'资源清单'}},
 {path:'/resources/new',component:()=>import('../features/v3/ResourceRegister.vue'),meta:{title:'登记资源'}},
 {path:'/resources/import',component:()=>import('../features/v3/ImportPage.vue'),meta:{title:'导入资源'}},
 {path:'/resources/:id',component:()=>import('../features/v3/ResourceDetail.vue'),meta:{title:'资源详情'}},
 {path:'/directory/:kind/:id',component:()=>import('../features/v3/DirectoryDetail.vue'),meta:{title:'目录详情'}},
 {path:'/my-resources',component:()=>import('../features/v3/ResourcesPage.vue'),meta:{title:'我的资源'}},
 {path:'/subscriptions',component:()=>import('../features/v3/SubscriptionsPage.vue'),meta:{title:'订阅与费用'}},
 {path:'/governance',component:()=>import('../features/v3/GovernancePage.vue'),meta:{title:'流程治理'}},
 {path:'/asset-map',component:()=>import('../features/v3/AssetMap.vue'),meta:{title:'资产地图'}},
 {path:'/settings',component:()=>import('../features/v3/SettingsPage.vue'),meta:{title:'设置与团队'}},
 {path:'/:pathMatch(.*)*',component:()=>import('../features/v3/NotFound.vue'),meta:{title:'页面不存在'}},
],scrollBehavior:()=>({top:0})});
const scrollPositions=new Map<string,number>();
router.beforeEach((to,from)=>{if(to.path!==from.path){const main=document.getElementById('workspace');if(main)scrollPositions.set(from.fullPath,main.scrollTop);if(scrollPositions.size>100)scrollPositions.delete(scrollPositions.keys().next().value!);}});
router.afterEach((to,from)=>{if(to.path!==from.path)void nextTick(()=>{const main=document.getElementById('workspace');if(main)main.scrollTop=scrollPositions.get(to.fullPath)??0;});document.title=`${String(to.meta.title??'数字资产')} · 数字资产管理中台`;});
