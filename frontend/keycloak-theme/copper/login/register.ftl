<#import "template.ftl" as layout>
<#import "user-profile-commons.ftl" as userProfileCommons>
<#import "register-commons.ftl" as register>
<@layout.registrationLayout displayMessage=messagesPerField.exists('global'); section>
 <#if section = "header">${msg("registerTitle")}
 <#elseif section = "form">
  <form id="kc-register-form" class="auth-form" action="${url.registrationAction}" method="post">
   <@userProfileCommons.userProfileFormFields; callback, attribute>
    <#if callback == "afterField" && passwordRequired?? && (attribute.name == 'username' || (attribute.name == 'email' && realm.registrationEmailAsUsername))>
     <div class="auth-field"><label class="auth-label" for="password">${msg("password")}</label><input id="password" name="password" type="password" class="auth-input" autocomplete="new-password" required aria-invalid="${messagesPerField.existsError('password')?c}" /><#if messagesPerField.existsError('password')><span class="auth-error" role="alert">${kcSanitize(messagesPerField.get('password'))?no_esc}</span></#if></div>
     <div class="auth-field"><label class="auth-label" for="password-confirm">${msg("passwordConfirm")}</label><input id="password-confirm" name="password-confirm" type="password" class="auth-input" autocomplete="new-password" required aria-invalid="${messagesPerField.existsError('password-confirm')?c}" /><#if messagesPerField.existsError('password-confirm')><span class="auth-error" role="alert">${kcSanitize(messagesPerField.get('password-confirm'))?no_esc}</span></#if></div>
    </#if>
   </@userProfileCommons.userProfileFormFields>
   <@register.termsAcceptance/>
   <#if recaptchaRequired??><div class="g-recaptcha" data-sitekey="${recaptchaSiteKey}" data-action="${recaptchaAction}"></div></#if>
   <button type="submit" class="auth-submit">${msg("doRegister")}</button>
   <a class="auth-link" href="${url.loginUrl}">${msg("doLogIn")}</a>
  </form>
 </#if>
</@layout.registrationLayout>

