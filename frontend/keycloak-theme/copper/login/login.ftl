<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username','password') displayInfo=realm.password && realm.registrationAllowed && !registrationDisabled??; section>
 <#if section = "header">${msg("loginAccountTitle")}
 <#elseif section = "form">
  <form id="kc-form-login" class="auth-form" action="${url.loginAction}" method="post">
   <#if !usernameHidden??>
    <div class="auth-field"><label for="username" class="auth-label">${msg("email")}</label><input id="username" class="auth-input" name="username" value="${(login.username!'')}" type="text" autocomplete="username" autofocus required aria-invalid="${messagesPerField.existsError('username','password')?c}" /></div>
   </#if>
   <div class="auth-field"><label for="password" class="auth-label">${msg("password")}</label><input id="password" class="auth-input" name="password" type="password" autocomplete="current-password" required aria-invalid="${messagesPerField.existsError('username','password')?c}" />
    <#if messagesPerField.existsError('username','password')><span class="auth-error" role="alert">${kcSanitize(messagesPerField.getFirstError('username','password'))?no_esc}</span></#if>
   </div>
   <#if realm.rememberMe && !usernameHidden??><label class="auth-check"><input name="rememberMe" type="checkbox" <#if login.rememberMe??>checked</#if> />${msg("rememberMe")}</label></#if>
   <input type="hidden" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if> />
   <button type="submit" class="auth-submit" name="login" id="kc-login">${msg("doLogIn")}</button>
   <#if realm.resetPasswordAllowed><a href="${url.loginResetCredentialsUrl}" class="auth-link">${msg("doForgotPassword")}</a></#if>
  </form>
 <#elseif section = "info"><a href="${url.registrationUrl}">${msg("doRegister")}</a>
 </#if>
</@layout.registrationLayout>
