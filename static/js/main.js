document.addEventListener('DOMContentLoaded',()=>{
  const navSearch=document.getElementById('searchInput');
  const heroSearch=document.getElementById('heroSearch');
  const catTags=document.querySelectorAll('.cat-tag');
  const grid=document.getElementById('toolGrid');
  const cards=grid?grid.querySelectorAll('.card'):[];
  const noRes=document.getElementById('noResults');
  let activeCat='';

  function filter(){
    const q=(navSearch?.value||heroSearch?.value||'').toLowerCase();
    let found=0;
    cards.forEach(c=>{
      const name=c.dataset.name||'';
      const desc=c.dataset.desc||'';
      const ct=c.dataset.cat||'';
      const ok=!activeCat||ct===activeCat;
      const match=ok&&(!q||name.includes(q)||desc.includes(q)||ct.includes(q));
      c.style.display=match?'':'none';
      if(match)found++;
    });
    if(noRes)noRes.style.display=found?'none':'block';
  }

  function setCat(cat){
    activeCat=cat||'';
    catTags.forEach(t=>t.classList.toggle('active',t.dataset.cat===activeCat));
    filter();
  }

  // Search sync
  if(navSearch)navSearch.addEventListener('input',()=>{if(heroSearch)heroSearch.value=navSearch.value;filter()});
  if(heroSearch)heroSearch.addEventListener('input',()=>{if(navSearch)navSearch.value=heroSearch.value;filter()});

  // Category buttons
  catTags.forEach(t=>t.addEventListener('click',()=>setCat(t.dataset.cat)));

  // Hot tags: check if it matches a category name, otherwise use as search
  document.querySelectorAll('.htag').forEach(ht=>{
    ht.addEventListener('click',e=>{
      e.preventDefault();
      const term=ht.textContent.trim();
      // Check if this matches a category name
      let matched=false;
      catTags.forEach(ct=>{if(ct.textContent.trim()===term){setCat(ct.dataset.cat);matched=true;}});
      if(!matched){
        if(heroSearch)heroSearch.value=term;
        if(navSearch)navSearch.value=term;
        setCat('');
      }
    });
  });
});
