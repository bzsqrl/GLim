// FFMaker FFGL runtime. This file is fixed; everything shader-specific lives
// in the generated ShaderData.h.
#include "FFMakerPlugin.h"
#include "ShaderData.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <ctime>

using namespace ffglex;

static CFFGLPluginInfo PluginInfo(
	PluginFactory< FFMakerPlugin >,
	FFM_PLUGIN_ID,
	FFM_PLUGIN_NAME,
	2, 1,// FFGL API version
	1, 0,// plugin version
	FFM_PLUGIN_TYPE,
	FFM_DESCRIPTION,
	FFM_ABOUT );

static const char* kVertexShader = R"(#version 410 core
layout( location = 0 ) in vec4 vPosition;
layout( location = 1 ) in vec2 vUV;
out vec2 ffm_uv;
void main()
{
	gl_Position = vPosition;
	ffm_uv      = vUV;
}
)";

static std::string JoinChunks( const char* const* chunks )
{
	std::string s;
	for( int i = 0; chunks[ i ]; ++i )
		s += chunks[ i ];
	return s;
}

static void FFM_HSVtoRGB( float h, float s, float v, float& r, float& g, float& b )
{
	h       = h - std::floor( h );
	float i = std::floor( h * 6.0f );
	float f = h * 6.0f - i;
	float p = v * ( 1.0f - s ), q = v * ( 1.0f - f * s ), t = v * ( 1.0f - ( 1.0f - f ) * s );
	switch( (int)i % 6 )
	{
	case 0: r = v, g = t, b = p; break;
	case 1: r = q, g = v, b = p; break;
	case 2: r = p, g = v, b = t; break;
	case 3: r = p, g = q, b = v; break;
	case 4: r = t, g = p, b = v; break;
	default: r = v, g = p, b = q; break;
	}
}

FFMakerPlugin::FFMakerPlugin()
{
	SetMinInputs( FFM_NUM_INPUTS );
	SetMaxInputs( FFM_NUM_INPUTS );

	for( int d = 0; d < FFM_NUM_PARAMS; ++d )
	{
		const FFMParamDef& p = FFM_PARAMS[ d ];
		firstHostParam.push_back( (int)hostParams.size() );
		auto add = [ & ]( const std::string& name, unsigned int type, float def, int sub ) {
			unsigned int idx = (unsigned int)hostParams.size();
			SetParamInfo( idx, name.c_str(), type, def );
			// SetParamInfo clamps defaults to 0..1; ranged params need the real default.
			if( ParamInfo* info = FindParamInfo( idx ) )
				info->defaultFloatVal = def;
			hostParams.push_back( { d, sub } );
			values.push_back( def );
			return idx;
		};
		std::string label = p.label;
		switch( p.kind )
		{
		case FFM_K_FLOAT:
		case FFM_K_SPEED:
			SetParamRange( add( label, FF_TYPE_STANDARD, p.def[ 0 ], 0 ), p.min[ 0 ], p.max[ 0 ] );
			break;
		case FFM_K_INT:
			SetParamRange( add( label, FF_TYPE_INTEGER, p.def[ 0 ], 0 ), p.min[ 0 ], p.max[ 0 ] );
			break;
		case FFM_K_BOOL:
		case FFM_K_MOUSECLICK:
			add( label, FF_TYPE_BOOLEAN, p.def[ 0 ], 0 );
			break;
		case FFM_K_EVENT:
			add( label, FF_TYPE_EVENT, 0.0f, 0 );
			break;
		case FFM_K_OPTION:
		{
			unsigned int idx = (unsigned int)hostParams.size();
			SetOptionParamInfo( idx, label.c_str(), (unsigned int)p.numOptions, p.def[ 0 ] );
			for( int o = 0; o < p.numOptions; ++o )
				SetParamElementInfo( idx, (unsigned int)o, p.optLabels[ o ], (float)o );
			hostParams.push_back( { d, 0 } );
			values.push_back( p.def[ 0 ] );
			break;
		}
		case FFM_K_COLOR:
			add( label, FF_TYPE_HUE, p.def[ 0 ], 0 );
			add( label + " Saturation", FF_TYPE_SATURATION, p.def[ 1 ], 1 );
			add( label + " Brightness", FF_TYPE_BRIGHTNESS, p.def[ 2 ], 2 );
			add( label + " Alpha", FF_TYPE_ALPHA, p.def[ 3 ], 3 );
			break;
		case FFM_K_POINT:
		case FFM_K_MOUSE:
			SetParamRange( add( label + " X", FF_TYPE_STANDARD, p.def[ 0 ], 0 ), p.min[ 0 ], p.max[ 0 ] );
			SetParamRange( add( label + " Y", FF_TYPE_STANDARD, p.def[ 1 ], 1 ), p.min[ 1 ], p.max[ 1 ] );
			break;
		}
	}
	targets.resize( FFM_NUM_TARGETS > 0 ? FFM_NUM_TARGETS : 0 );
}

FFMakerPlugin::~FFMakerPlugin()
{
}

FFResult FFMakerPlugin::InitGL( const FFGLViewportStruct* vp )
{
	shaders.clear();
	for( int i = 0; i < FFM_NUM_PROGRAMS; ++i )
	{
		std::string frag = JoinChunks( FFM_PROGRAMS[ i ] );
		shaders.emplace_back( new FFGLShader() );
		if( !shaders.back()->Compile( kVertexShader, frag.c_str() ) )
		{
			FFGLLog::LogToHost( "FFMaker: shader failed to compile" );
			DeInitGL();
			return FF_FAIL;
		}
	}
	if( !quad.Initialise() )
	{
		DeInitGL();
		return FF_FAIL;
	}
	glGenTextures( 1, &blackTex );
	glBindTexture( GL_TEXTURE_2D, blackTex );
	const unsigned char black[ 4 ] = { 0, 0, 0, 0 };
	glTexImage2D( GL_TEXTURE_2D, 0, GL_RGBA8, 1, 1, 0, GL_RGBA, GL_UNSIGNED_BYTE, black );
	glTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST );
	glTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST );
	glBindTexture( GL_TEXTURE_2D, 0 );
	return CFFGLPlugin::InitGL( vp );
}

FFResult FFMakerPlugin::DeInitGL()
{
	for( auto& s : shaders )
		s->FreeGLResources();
	shaders.clear();
	quad.Release();
	for( auto& t : targets )
		FreeTarget( t );
	if( blackTex )
		glDeleteTextures( 1, &blackTex );
	blackTex = 0;
	return FF_SUCCESS;
}

void FFMakerPlugin::AllocTarget( Target& t, int w, int h, bool isFloat )
{
	FreeTarget( t );
	t.w = w;
	t.h = h;
	GLfloat prevClear[ 4 ];
	glGetFloatv( GL_COLOR_CLEAR_VALUE, prevClear );
	glClearColor( 0, 0, 0, 0 );
	for( int i = 0; i < 2; ++i )
	{
		glGenTextures( 1, &t.tex[ i ] );
		glBindTexture( GL_TEXTURE_2D, t.tex[ i ] );
		glTexImage2D( GL_TEXTURE_2D, 0, isFloat ? GL_RGBA32F : GL_RGBA8, w, h, 0, GL_RGBA,
					  isFloat ? GL_FLOAT : GL_UNSIGNED_BYTE, nullptr );
		glTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR );
		glTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR );
		glTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE );
		glTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE );
		glGenFramebuffers( 1, &t.fbo[ i ] );
		glBindFramebuffer( GL_FRAMEBUFFER, t.fbo[ i ] );
		glFramebufferTexture2D( GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, t.tex[ i ], 0 );
		glClear( GL_COLOR_BUFFER_BIT );
	}
	glBindTexture( GL_TEXTURE_2D, 0 );
	glClearColor( prevClear[ 0 ], prevClear[ 1 ], prevClear[ 2 ], prevClear[ 3 ] );
}

void FFMakerPlugin::FreeTarget( Target& t )
{
	for( int i = 0; i < 2; ++i )
	{
		if( t.fbo[ i ] )
			glDeleteFramebuffers( 1, &t.fbo[ i ] );
		if( t.tex[ i ] )
			glDeleteTextures( 1, &t.tex[ i ] );
		t.fbo[ i ] = t.tex[ i ] = 0;
	}
	t.w = t.h = 0;
}

float FFMakerPlugin::Value( int def, int sub ) const
{
	return values[ firstHostParam[ def ] + sub ];
}

float FFMakerPlugin::P( const char* uniform ) const
{
	for( int d = 0; d < FFM_NUM_PARAMS; ++d )
		if( FFM_PARAMS[ d ].uniform[ 0 ] && strcmp( FFM_PARAMS[ d ].uniform, uniform ) == 0 )
			return Value( d, 0 );
	return 0.0f;
}

void FFMakerPlugin::SendParams( GLuint program )
{
	const float W = (float)currentViewport.width, H = (float)currentViewport.height;
	for( int d = 0; d < FFM_NUM_PARAMS; ++d )
	{
		const FFMParamDef& p = FFM_PARAMS[ d ];
		if( !p.uniform[ 0 ] )
			continue;
		GLint loc = glGetUniformLocation( program, p.uniform );
		if( loc < 0 )
			continue;
		switch( p.kind )
		{
		case FFM_K_FLOAT:
			glUniform1f( loc, Value( d, 0 ) );
			break;
		case FFM_K_INT:
			glUniform1i( loc, (int)std::lround( Value( d, 0 ) ) );
			break;
		case FFM_K_BOOL:
		case FFM_K_EVENT:
			glUniform1i( loc, Value( d, 0 ) > 0.5f ? 1 : 0 );
			break;
		case FFM_K_OPTION:
		{
			int o = std::max( 0, std::min( p.numOptions - 1, (int)std::lround( Value( d, 0 ) ) ) );
			glUniform1i( loc, (int)p.optValues[ o ] );
			break;
		}
		case FFM_K_COLOR:
		{
			float hue = Value( d, 0 );
			float r, g, b;
			FFM_HSVtoRGB( hue >= 1.0f ? 0.0f : hue, Value( d, 1 ), Value( d, 2 ), r, g, b );
			if( p.glslComponents == 3 )
				glUniform3f( loc, r, g, b );
			else
				glUniform4f( loc, r, g, b, Value( d, 3 ) );
			break;
		}
		case FFM_K_POINT:
		{
			float x = Value( d, 0 ), y = Value( d, 1 );
			if( p.pixelSpace )
				x *= W, y *= H;
			glUniform2f( loc, x, y );
			break;
		}
		}
	}
}

FFResult FFMakerPlugin::ProcessOpenGL( ProcessOpenGLStruct* pGL )
{
	if( shaders.empty() )
		return FF_FAIL;

	// ── Clock: real time, scaled by Speed and accumulated so Speed changes never jump.
	auto now = std::chrono::steady_clock::now();
	float dt = hasLastTick ? std::chrono::duration< float >( now - lastTick ).count() : 0.0f;
	lastTick    = now;
	hasLastTick = true;
	dt          = std::max( 0.0f, std::min( dt, 0.25f ) );
	float speed = 1.0f;
	float mouseX = 0.0f, mouseY = 0.0f;
	bool mouseDown = false;
	for( int d = 0; d < FFM_NUM_PARAMS; ++d )
	{
		if( FFM_PARAMS[ d ].kind == FFM_K_SPEED )
			speed = Value( d, 0 );
		else if( FFM_PARAMS[ d ].kind == FFM_K_MOUSE )
			mouseX = Value( d, 0 ), mouseY = Value( d, 1 );
		else if( FFM_PARAMS[ d ].kind == FFM_K_MOUSECLICK )
			mouseDown = Value( d, 0 ) > 0.5f;
	}
	lastDelta = dt * speed;
	clockTime += lastDelta;
	std::time_t tt = std::time( nullptr );
	std::tm lt;
#ifdef _WIN32
	localtime_s( &lt, &tt );
#else
	localtime_r( &tt, &lt );
#endif
	float daySeconds = (float)( lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec );

	const int VW = (int)currentViewport.width, VH = (int)currentViewport.height;
	GLboolean scissor = glIsEnabled( GL_SCISSOR_TEST );
	glDisable( GL_SCISSOR_TEST );

	for( int pi = 0; pi < FFM_NUM_PASSES; ++pi )
	{
		const FFMPassDef& pass = FFM_PASSES[ pi ];
		int w = VW, h = VH;
		if( pass.target >= 0 )
		{
			float fw = (float)VW, fh = (float)VH;
			FFM_PassSize( pi, (float)VW, (float)VH, *this, fw, fh );
			w          = std::max( 1, (int)fw );
			h          = std::max( 1, (int)fh );
			Target& t  = targets[ pass.target ];
			if( t.w != w || t.h != h )
				AllocTarget( t, w, h, FFM_TARGETS[ pass.target ].isFloat != 0 );
			glBindFramebuffer( GL_FRAMEBUFFER, t.fbo[ 1 - t.front ] );
		}
		else
		{
			glBindFramebuffer( GL_FRAMEBUFFER, pGL->HostFBO );
		}
		glViewport( 0, 0, w, h );

		GLuint prog = shaders[ pass.program ]->GetGLID();
		glUseProgram( prog );
		glUniform2f( glGetUniformLocation( prog, "ffm_Resolution" ), (float)w, (float)h );
		glUniform1f( glGetUniformLocation( prog, "ffm_Time" ), (float)clockTime );
		glUniform1f( glGetUniformLocation( prog, "ffm_TimeDelta" ), lastDelta );
		glUniform1i( glGetUniformLocation( prog, "ffm_Frame" ), frame );
		glUniform1i( glGetUniformLocation( prog, "ffm_PassIndex" ), pi );
		glUniform4f( glGetUniformLocation( prog, "ffm_Date" ), (float)( lt.tm_year + 1900 ), (float)lt.tm_mon,
					 (float)lt.tm_mday, daySeconds );
		float mx = mouseX * w, my = mouseY * h;
		glUniform4f( glGetUniformLocation( prog, "ffm_Mouse" ), mx, my, mouseDown ? mx : -mx, mouseDown ? my : -my );
		SendParams( prog );

		int unit = 0;
		for( int s = 0; s < FFM_NUM_SAMPLERS; ++s )
		{
			const FFMSamplerDef& sd = FFM_SAMPLERS[ s ];
			GLint loc = glGetUniformLocation( prog, sd.name );
			if( loc < 0 )
				continue;
			GLuint tex = blackTex;
			if( sd.source == FFM_SRC_HOST && (unsigned)sd.index < pGL->numInputTextures && pGL->inputTextures[ sd.index ] )
				tex = pGL->inputTextures[ sd.index ]->Handle;
			else if( sd.source == FFM_SRC_TARGET && targets[ sd.index ].tex[ 0 ] )
				tex = targets[ sd.index ].tex[ targets[ sd.index ].front ];
			glActiveTexture( GL_TEXTURE0 + unit );
			glBindTexture( GL_TEXTURE_2D, tex );
			glUniform1i( loc, unit );
			++unit;
		}

		quad.Draw();

		for( int u = unit - 1; u >= 0; --u )
		{
			glActiveTexture( GL_TEXTURE0 + u );
			glBindTexture( GL_TEXTURE_2D, 0 );
		}
		if( pass.target >= 0 )
			targets[ pass.target ].front = 1 - targets[ pass.target ].front;
	}

	// If every pass rendered to a buffer, show the last one.
	if( FFM_NUM_PASSES > 0 && FFM_PASSES[ FFM_NUM_PASSES - 1 ].target >= 0 )
	{
		Target& t = targets[ FFM_PASSES[ FFM_NUM_PASSES - 1 ].target ];
		glBindFramebuffer( GL_READ_FRAMEBUFFER, t.fbo[ t.front ] );
		glBindFramebuffer( GL_DRAW_FRAMEBUFFER, pGL->HostFBO );
		glBlitFramebuffer( 0, 0, t.w, t.h, 0, 0, VW, VH, GL_COLOR_BUFFER_BIT, GL_LINEAR );
	}

	glUseProgram( 0 );
	glActiveTexture( GL_TEXTURE0 );
	glBindFramebuffer( GL_FRAMEBUFFER, pGL->HostFBO );
	glViewport( currentViewport.x, currentViewport.y, currentViewport.width, currentViewport.height );
	if( scissor )
		glEnable( GL_SCISSOR_TEST );

	// Events are one-frame pulses.
	for( size_t i = 0; i < hostParams.size(); ++i )
		if( FFM_PARAMS[ hostParams[ i ].def ].kind == FFM_K_EVENT )
			values[ i ] = 0.0f;
	++frame;
	return FF_SUCCESS;
}

FFResult FFMakerPlugin::SetFloatParameter( unsigned int index, float value )
{
	if( index >= values.size() )
		return FF_FAIL;
	values[ index ] = value;
	return FF_SUCCESS;
}

float FFMakerPlugin::GetFloatParameter( unsigned int index )
{
	return index < values.size() ? values[ index ] : 0.0f;
}

char* FFMakerPlugin::GetParameterDisplay( unsigned int index )
{
	static char buf[ 32 ];
	if( index >= values.size() )
		return (char*)FF_FAIL;
	const FFMParamDef& p = FFM_PARAMS[ hostParams[ index ].def ];
	if( p.kind == FFM_K_OPTION )
	{
		int o = std::max( 0, std::min( p.numOptions - 1, (int)std::lround( values[ index ] ) ) );
		snprintf( buf, sizeof( buf ), "%s", p.optLabels[ o ] );
	}
	else if( p.kind == FFM_K_INT )
		snprintf( buf, sizeof( buf ), "%d", (int)std::lround( values[ index ] ) );
	else
		snprintf( buf, sizeof( buf ), "%.3f", values[ index ] );
	return buf;
}
