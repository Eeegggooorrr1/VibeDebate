<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false displayWide=false displaySocialProviders=false>
<!doctype html>
<html lang="${(locale.currentLanguageTag)!'ru'}">
<head>
 <meta charset="utf-8" />
 <meta name="viewport" content="width=device-width, initial-scale=1" />
 <meta name="theme-color" content="#211b18" />
 <title>VibeDebate</title>
 <link rel="stylesheet" href="${url.resourcesPath}/css/copper.css" />
 <#if scripts??><#list scripts as script><script src="${script}" defer></script></#list></#if>
</head>
<body class="custom-auth ${bodyClass}">
 <div class="auth-shell">
  <header class="auth-header"><a href="${url.loginUrl}" class="auth-wordmark">VibeDebate</a></header>
  <main class="auth-panel">
   <h1><#nested "header"></h1>
   <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
    <div class="auth-message auth-message--${message.type}" role="alert">${kcSanitize(message.summary)?no_esc}</div>
   </#if>
   <#nested "form">
   <#if displayInfo><div class="auth-footer"><#nested "info"></div></#if>
   <#nested "socialProviders">
  </main>
 </div>
 <script src="${url.resourcesPath}/js/copper.js" defer></script>
</body>
</html>
</#macro>
