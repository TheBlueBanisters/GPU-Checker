import React from 'react';import {createRoot} from 'react-dom/client';import App from './App';import './style.css';
const flex=document.createElement('div');flex.style.cssText='display:flex;flex-direction:column;row-gap:1px;position:absolute;visibility:hidden';flex.append(document.createElement('div'),document.createElement('div'));document.body.append(flex);if(flex.scrollHeight!==1)document.documentElement.classList.add('no-flex-gap');flex.remove();
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
